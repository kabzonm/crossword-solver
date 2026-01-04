# ארכיטקטורת הסולבר החדש

## תוכן עניינים
1. [רקע ובעיות במצב הקיים](#1-רקע-ובעיות-במצב-הקיים)
2. [עקרונות מנחים](#2-עקרונות-מנחים)
3. [מבני נתונים](#3-מבני-נתונים)
4. [זרימת האלגוריתם](#4-זרימת-האלגוריתם)
5. [שיפורי Prompt](#5-שיפורי-prompt)
6. [מבנה קבצים](#6-מבנה-קבצים)
7. [דוגמאות](#7-דוגמאות)

---

## 1. רקע ובעיות במצב הקיים

### האלגוריתם הנוכחי
- CSP (Constraint Satisfaction Problem) עם Backtracking
- שואל את Claude הגדרה-הגדרה
- בוחר הגדרה לפי "קושי" (אורך, אותיות ידועות)
- מגבלת 100 backtracks

### בעיות שזוהו

| בעיה | תיאור |
|------|-------|
| **אין אינדקס** | לא ניתן לסנן מהר מועמדים לפי תבנית אותיות |
| **אין רמות ביטחון להגדרות** | "במבה" ו"אות באנגלית" מקבלות אותה עדיפות |
| **אין Re-query** | גם אחרי שגילינו 50% מהאותיות, לא שואלים שוב |
| **שיבוץ אות-אות** | הסולבר יכול "להמציא" אותיות במקום מילים שלמות |
| **Prompt בסיסי** | לא תומך בפורמט (3,2) למילים מרובות או ר"ת |

---

## 2. עקרונות מנחים

### 2.1 אינדקס לסינון מהיר
מבנה נתונים שמאפשר לשאול:
> "איזה מילים באורך 5 מתאימות לתבנית `_ב_מ_`?"

### 2.2 ביטחון בהגדרה (Clue Certainty)
לכל הגדרה יש "ודאות" - כמה תשובות סבירות יש לה:
- **ודאות גבוהה (0.9-1.0)**: "במבה", "מרבד קסמים" - תשובה אחת ברורה
- **ודאות בינונית (0.5-0.8)**: "עיר בישראל" - כמה עשרות אפשרויות
- **ודאות נמוכה (0.1-0.4)**: "אות באנגלית" - 26 אפשרויות

### 2.3 Re-Query דינמי
כאשר מתגלות **30% אותיות חדשות** מאז השאילתא האחרונה - שואלים שוב עם ההקשר החדש.

### 2.4 מילים שלמות בלבד
הסולבר **לא ממציא אותיות** - רק משבץ מילים שלמות שהתקבלו מ-Claude.

### 2.5 תמיכה בפורמטים מיוחדים
- **פורמט (3,2)**: תשובה בת 2 מילים (3 אותיות + 2 אותיות) → נכתבת ללא רווח
- **ר"ת (ראשי תיבות)**: התשובה היא ראשי תיבות

---

## 3. מבני נתונים

### 3.1 CandidateWord
מייצג מועמד לתשובה:

```python
@dataclass
class CandidateWord:
    word: str                      # המילה עצמה ("במבה")
    clue_id: str                   # מאיזה clue הגיעה
    confidence: float              # ביטחון ב-תשובה הזו (0.0-1.0)
    clue_certainty: float          # ודאות ההגדרה (0.0-1.0)
    query_phase: int               # באיזה שלב התקבלה (1, 2, 3...)
    known_letters_snapshot: str    # תבנית בזמן השאילתא ("____" או "_ב__")
```

### 3.2 CandidateIndex
אינדקס מרכזי לכל המועמדים:

```python
class CandidateIndex:
    # מיפוי לפי אורך
    by_length: Dict[int, List[CandidateWord]]
    # מיפוי לפי clue_id
    by_clue: Dict[str, List[CandidateWord]]
    # מיפוי לפי (מיקום, אות) - לסינון מהיר
    by_position_letter: Dict[Tuple[int, str], Set[str]]  # (pos, letter) → {words}

    def get_matching(self, length: int, pattern: str) -> List[CandidateWord]:
        """מחזיר מועמדים שמתאימים לאורך ולתבנית"""

    def filter_by_letter(self, position: int, letter: str) -> None:
        """מסנן מועמדים שלא מתאימים לאות במיקום מסוים"""

    def remove_candidate(self, clue_id: str, word: str) -> None:
        """מסיר מועמד ספציפי (אחרי כישלון)"""
```

### 3.3 ClueState
מצב הגדרה בתהליך הפתרון:

```python
@dataclass
class ClueState:
    clue: ClueEntry
    candidates: List[CandidateWord]  # מועמדים נותרים
    is_solved: bool = False
    placed_word: Optional[str] = None
    last_query_phase: int = 0        # מתי נשאל לאחרונה
    known_letters_at_query: str = "" # מה היו האותיות בשאילתא האחרונה
```

### 3.4 SolverState
מצב כללי של הפתרון:

```python
@dataclass
class SolverState:
    clue_states: Dict[str, ClueState]
    candidate_index: CandidateIndex
    current_phase: int = 1
    total_letters_discovered: int = 0
    letters_since_last_query: int = 0
    placement_stack: List[Tuple[str, str]]  # [(clue_id, word), ...]
    tried_and_failed: Dict[str, Set[str]]   # clue_id → {failed words}
```

---

## 4. זרימת האלגוריתם

### Phase 1: Initial Query (שאילתא ראשונית)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PHASE 1                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. אסוף את כל ההגדרות מ-ClueDatabase                           │
│                                                                  │
│  2. שלח ל-Claude בקבוצות (batch של 10):                         │
│     - טקסט ההגדרה                                               │
│     - אורך התשובה                                                │
│     - תבנית אותיות ידועות (בד"כ ריקה בהתחלה)                    │
│                                                                  │
│  3. בקש מ-Claude:                                                │
│     - 10 תשובות אפשריות לכל הגדרה                               │
│     - ציון ביטחון (confidence) לכל תשובה                        │
│     - ציון ודאות (clue_certainty) להגדרה עצמה                   │
│                                                                  │
│  4. בנה CandidateIndex מכל התשובות                              │
│                                                                  │
│  5. המשך ל-Phase 2                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2: Constraint Propagation (הפצת אילוצים)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PHASE 2                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  לולאה עד שנתקעים או מסיימים:                                   │
│                                                                  │
│  1. מצא את ההגדרה הטובה ביותר לשיבוץ:                           │
│     - יש לה מועמד אחד תקין בלבד, או                             │
│     - המועמד הראשון שלה עם confidence > 0.9                     │
│     - עדיפות להגדרות עם clue_certainty גבוה                     │
│                                                                  │
│  2. שבץ את המילה השלמה (לא אותיות בודדות!)                      │
│     - עדכן SolutionGrid                                         │
│     - הוסף ל-placement_stack                                    │
│                                                                  │
│  3. עדכן את CandidateIndex:                                     │
│     - סנן מועמדים שלא מתאימים לאותיות החדשות                    │
│     - עדכן known_letters בהגדרות מצטלבות                        │
│                                                                  │
│  4. ספור אותיות חדשות:                                          │
│     letters_since_last_query += len(new_letters)                 │
│                                                                  │
│  5. בדוק אם צריך Re-Query:                                      │
│     if letters_since_last_query >= 0.3 * total_solution_cells:  │
│         → עבור ל-Phase 3                                        │
│                                                                  │
│  6. אם אין מועמד תקין לאף הגדרה:                                │
│     → עבור ל-Phase 4 (Backtrack)                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 3: Re-Query (שאילתא מחודשת)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PHASE 3                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  תנאי כניסה: התגלו >= 30% אותיות חדשות מאז השאילתא האחרונה     │
│                                                                  │
│  1. סנן הגדרות לשאילתא מחודשת:                                  │
│     - לא נפתרו עדיין                                            │
│     - יש להן אותיות ידועות חדשות                                │
│     - known_letters השתנה מאז last_query                        │
│                                                                  │
│  2. שלח ל-Claude עם הקשר מעודכן:                                │
│     "הגדרה: X, אורך: 5, תבנית: _ב_מ_"                           │
│                                                                  │
│  3. מזג תשובות חדשות ל-CandidateIndex:                          │
│     - אם תשובה קיימת: עדכן confidence (ממוצע משוקלל)            │
│     - אם תשובה חדשה: הוסף עם query_phase נוכחי                  │
│                                                                  │
│  4. אפס את letters_since_last_query                             │
│                                                                  │
│  5. העלה את current_phase ב-1                                   │
│                                                                  │
│  6. חזור ל-Phase 2                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 4: Backtracking (חזרה אחורה)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PHASE 4                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  תנאי כניסה: אין מועמד תקין לאף הגדרה שלא נפתרה                 │
│                                                                  │
│  1. בדוק מגבלת backtracks:                                      │
│     if backtracks >= MAX_BACKTRACKS:                            │
│         → סיים עם סטטוס STUCK                                   │
│                                                                  │
│  2. מצא את השיבוץ האחרון שאינו ידני:                            │
│     clue_id, word = placement_stack.pop()                        │
│     if clue was manual:                                          │
│         → אין לאן לחזור, סיים עם STUCK                          │
│                                                                  │
│  3. הסר את המילה מ-SolutionGrid                                 │
│                                                                  │
│  4. סמן את המילה כ"נכשלה":                                      │
│     tried_and_failed[clue_id].add(word)                         │
│                                                                  │
│  5. עדכן מחדש את known_letters בהגדרות מצטלבות                  │
│                                                                  │
│  6. backtracks += 1                                              │
│                                                                  │
│  7. חזור ל-Phase 2                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### תרשים זרימה כללי

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                         ▼
              ┌──────────────────┐
              │    PHASE 1       │
              │  Initial Query   │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
         ┌───►│    PHASE 2       │◄───────────┐
         │    │   Propagation    │            │
         │    └────────┬─────────┘            │
         │             │                      │
         │    ┌────────┴────────┐             │
         │    │                 │             │
         │    ▼                 ▼             │
         │  מועמד          אין מועמד         │
         │  נמצא           תקין              │
         │    │                 │             │
         │    ▼                 ▼             │
         │  שבץ         ┌──────────────┐      │
         │  מילה        │   PHASE 4    │      │
         │    │         │  Backtrack   │      │
         │    │         └──────┬───────┘      │
         │    │                │              │
         │    ▼                │              │
         │  >= 30%             │              │
         │  אותיות?            │              │
         │    │                │              │
         │  Yes     No         │              │
         │    │      │         │              │
         │    ▼      └─────────┼──────────────┘
         │ ┌──────────────┐    │
         │ │   PHASE 3    │    │
         │ │   Re-Query   │────┘
         │ └──────────────┘
         │
         │    הכל נפתר?
         │        │
         │      Yes
         │        ▼
         │   ┌─────────┐
         └───│  DONE   │
             └─────────┘
```

---

## 5. שיפורי Prompt

### 5.1 Prompt לשאילתא בודדת

```python
SOLVE_PROMPT_V2 = """You are a Hebrew crossword puzzle expert.

Clue: "{clue_text}"
Answer length: {length} letters
{pattern_info}

SPECIAL FORMATS:
1. If the clue shows "(3,2)" or similar - this means a multi-word answer:
   - (3,2) = 3 letters + 2 letters = 5 total, written WITHOUT spaces
   - Example: "לב טוב" with (3,2) → answer is "לבטוב" (5 letters)

2. If the clue contains 'ר"ת' or "ראשי תיבות" - give an ACRONYM:
   - Example: 'ארצות הברית (ר"ת)' → "ארהב"
   - Example: 'צבא הגנה לישראל (ר"ת)' → "צהל"

RESPOND WITH JSON ONLY:
{{
  "clue_certainty": 0.85,
  "candidates": [
    {{"answer": "תשובה", "confidence": 0.95}},
    {{"answer": "אפשרות", "confidence": 0.75}},
    ...
  ]
}}

FIELD EXPLANATIONS:
- clue_certainty: How "narrow" is this clue?
  - 1.0 = Only one possible answer (e.g., "במבה", "חטיף ישראלי מפורסם")
  - 0.5 = A few dozen options (e.g., "עיר בישראל")
  - 0.1 = Many options (e.g., "אות באנגלית", "מספר")

- confidence: Your certainty that THIS SPECIFIC answer is correct
  - 0.95+ = Very confident
  - 0.7-0.9 = Likely correct
  - 0.5-0.7 = Possible
  - <0.5 = Guess

RULES:
1. Each answer must be EXACTLY {length} Hebrew letters
2. NO spaces, NO punctuation - just Hebrew letters
3. {pattern_constraint}
4. Provide up to 10 candidates, sorted by confidence (highest first)
5. For common/famous clues (brands, songs, etc.) - confidence should be high
6. For ambiguous clues - confidence should be lower, provide more variety
"""
```

### 5.2 Prompt לשאילתא קבוצתית (Batch)

```python
BATCH_SOLVE_PROMPT_V2 = """You are a Hebrew crossword puzzle expert. Solve these clues.

{clues_list}

SPECIAL FORMATS:
- "(3,2)" means multi-word answer written without spaces
- 'ר"ת' means acronym

RESPOND WITH JSON ONLY:
{{
  "solutions": [
    {{
      "clue_id": "clue_0_0_full",
      "clue_certainty": 0.9,
      "candidates": [
        {{"answer": "תשובה", "confidence": 0.95}},
        ...
      ]
    }},
    ...
  ]
}}

Remember:
- clue_certainty = how narrow is the clue (1.0=one answer, 0.1=many)
- confidence = how sure you are about each specific answer
- All answers must be EXACT length specified, Hebrew only, no spaces
"""
```

### 5.3 פורמט רשימת הגדרות ב-Batch

```python
def format_clue_for_batch(clue: ClueEntry) -> str:
    pattern = clue.get_constraint_string()

    result = f"""- ID: {clue.id}
  Clue: "{clue.text}"
  Length: {clue.answer_length} letters"""

    if pattern and '_' not in pattern:
        # יש אותיות ידועות
        result += f"\n  Known pattern: {pattern}"

    return result
```

---

## 6. מבנה קבצים

### קבצים חדשים

```
services/
├── puzzle_solver.py          # קיים - יעודכן
├── clue_solver.py            # קיים - יעודכן (prompts חדשים)
├── clue_database.py          # קיים - ללא שינוי
├── solution_grid.py          # קיים - ללא שינוי
│
├── candidate_index.py        # חדש! - CandidateIndex, CandidateWord
└── solver_strategy.py        # חדש! - SolverState, ClueState, לוגיקת phases
```

### candidate_index.py

```python
"""
Candidate Index - אינדקס מהיר למועמדים
"""

@dataclass
class CandidateWord:
    word: str
    clue_id: str
    confidence: float
    clue_certainty: float
    query_phase: int
    known_letters_snapshot: str

class CandidateIndex:
    def __init__(self):
        self.by_length: Dict[int, List[CandidateWord]] = {}
        self.by_clue: Dict[str, List[CandidateWord]] = {}
        self._position_index: Dict[Tuple[int, str], Set[str]] = {}

    def add_candidate(self, candidate: CandidateWord) -> None: ...
    def get_candidates_for_clue(self, clue_id: str) -> List[CandidateWord]: ...
    def get_matching_pattern(self, length: int, pattern: str) -> List[CandidateWord]: ...
    def filter_incompatible(self, clue_id: str, position: int, letter: str) -> int: ...
    def remove_candidate(self, clue_id: str, word: str) -> None: ...
    def get_statistics(self) -> Dict: ...
```

### solver_strategy.py

```python
"""
Solver Strategy - אסטרטגיית הפתרון
"""

@dataclass
class ClueState:
    clue: ClueEntry
    is_solved: bool = False
    placed_word: Optional[str] = None
    last_query_phase: int = 0
    known_letters_at_query: str = ""

@dataclass
class SolverState:
    clue_states: Dict[str, ClueState]
    candidate_index: CandidateIndex
    current_phase: int = 1
    total_solution_cells: int = 0
    letters_discovered: int = 0
    letters_since_query: int = 0
    placement_stack: List[Tuple[str, str]] = field(default_factory=list)
    tried_and_failed: Dict[str, Set[str]] = field(default_factory=dict)
    backtracks: int = 0

class SolverStrategy:
    REQUERY_THRESHOLD = 0.3  # 30% אותיות חדשות
    MAX_BACKTRACKS = 100

    def __init__(self, clue_db: ClueDatabase, solution_grid: SolutionGrid,
                 clue_solver: ClueSolver): ...

    def solve(self) -> SolveProgress: ...
    def _phase1_initial_query(self) -> None: ...
    def _phase2_propagate(self) -> bool: ...
    def _phase3_requery(self) -> None: ...
    def _phase4_backtrack(self) -> bool: ...

    def _select_best_clue(self) -> Optional[ClueState]: ...
    def _place_word(self, clue_state: ClueState, word: str) -> None: ...
    def _update_intersections(self, clue: ClueEntry, word: str) -> int: ...
    def _should_requery(self) -> bool: ...
```

---

## 7. דוגמאות

### 7.1 דוגמה: פתרון הגדרה עם ודאות גבוהה

```
הגדרה: "חטיף תירס ישראלי מפורסם"
אורך: 4

תשובה מ-Claude:
{
  "clue_certainty": 0.98,  // הגדרה מאוד ברורה
  "candidates": [
    {"answer": "במבה", "confidence": 0.99},
    {"answer": "ביסל", "confidence": 0.15}
  ]
}

→ הסולבר ישבץ "במבה" מיד (confidence > 0.9 + certainty > 0.9)
```

### 7.2 דוגמה: פתרון הגדרה עם ודאות נמוכה

```
הגדרה: "אות באנגלית"
אורך: 2

תשובה מ-Claude:
{
  "clue_certainty": 0.1,  // הגדרה מעורפלת - 26 אפשרויות
  "candidates": [
    {"answer": "אי", "confidence": 0.15},
    {"answer": "בי", "confidence": 0.12},
    {"answer": "סי", "confidence": 0.10},
    ...
  ]
}

→ הסולבר ימתין - לא ישבץ עד שיהיו אותיות ידועות מהצלבות
```

### 7.3 דוגמה: Re-Query אחרי גילוי אותיות

```
מצב התחלתי:
- הגדרה "בעל כנפיים", אורך 5, תבנית: "_____"
- מועמדים: ציפור(0.7), פרפר(0.6), יונה(0.4)...

אחרי שיבוץ הגדרות מצטלבות:
- תבנית עודכנה ל: "_ר___"

בדיקת Re-Query:
- 30% מהאותיות התגלו → טריגר!

שאילתא חדשה:
"הגדרה: בעל כנפיים, אורך: 5, תבנית: _ר___"

תשובה חדשה מ-Claude:
{
  "clue_certainty": 0.85,
  "candidates": [
    {"answer": "עורב", "confidence": 0.88},  // חדש! מתאים לתבנית
    {"answer": "פרפר", "confidence": 0.75}   // עודכן
  ]
}

→ מזג ל-Index, עכשיו "עורב" הכי סביר
```

### 7.4 דוגמה: פורמט (3,2)

```
הגדרה: "מקום מנוחה (3,2)"
אורך: 5

פירוש: מילה בת 3 אותיות + מילה בת 2 אותיות = 5 אותיות ללא רווח

תשובה מ-Claude:
{
  "clue_certainty": 0.75,
  "candidates": [
    {"answer": "ביתאב", "confidence": 0.80},  // "בית אב"
    {"answer": "חדרשן", "confidence": 0.40}   // "חדר שן"
  ]
}
```

### 7.5 דוגמה: ר"ת (ראשי תיבות)

```
הגדרה: 'ארגון הבריאות העולמי (ר"ת)'
אורך: 4

תשובה מ-Claude:
{
  "clue_certainty": 0.95,
  "candidates": [
    {"answer": "אהבע", "confidence": 0.90},  // א.ה.ב.ע
    {"answer": "who", "confidence": 0.05}    // לא תקין - לא עברית
  ]
}
```

---

## סיכום

| רכיב | מצב קודם | מצב חדש |
|------|----------|---------|
| בחירת הגדרה | לפי קושי (אורך) | לפי **ביטחון + ודאות** |
| אינדקס מועמדים | אין (רק cache) | **CandidateIndex** עם אינדקסים |
| סינון | בזמן שיבוץ | **מיידי** אחרי כל שיבוץ |
| Re-query | אף פעם | **30% אותיות חדשות** |
| שיבוץ | אות-אות | **מילה שלמה בלבד** |
| Prompt | בסיסי | **תומך (3,2) ור"ת** |
| מדדים | רק confidence | **confidence + clue_certainty** |

---

*מסמך זה נכתב ב-2026-01-04 ומתאר את הארכיטקטורה המתוכננת לסולבר החדש.*
