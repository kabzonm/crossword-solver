# פיצ'ר: ממשק פתרון אינטראקטיבי - Interactive Solver UI

## תאריך: 2025-12-29

---

## 1. אפיון הפיצ'ר

### הבעיה הנוכחית
- סליידר התקדמות משעמם - המשתמש רק מסתכל על מספר שעולה
- אין ויזואליזציה של מה קורה בפועל
- אין אינטראקציה - המשתמש פסיבי לחלוטין

### הפתרון המוצע
ממשק אינטראקטיבי שמציג:
1. **גריד התשבץ בזמן אמת** - רואים אותיות נכתבות אות אחר אות
2. **טבלת הגדרות דינמית** - רואים כל הגדרה שנפתרת
3. **הדגשה ויזואלית** - המשבצות שנפתרות כרגע מודגשות
4. **סטטיסטיקות חיות** - אחוז פתרון, זמן, backtracks
5. **שליטה מלאה** - עצירה, עריכה ידנית, והמשך

### החלטות עיצוב מאושרות
- **תצוגת אותיות:** כל אות מופיעה בנפרד (לא כל המילה בבת אחת)
- **עריכה ידנית:** המשתמש יכול לעצור, לכתוב תשובות, ולהמשיך
- **אילוצים ידניים:** תשובות שהוכנסו ידנית הופכות לאילוץ קבוע שהמערכת לא יכולה לשנות

---

## 2. חווית המשתמש המלאה

### תרחיש רגיל (אוטומטי)
```
המשתמש לוחץ "▶ התחל פתרון"
    ↓
הגריד מופיע ריק עם מסגרות
    ↓
הגדרה ראשונה מודגשת בצהוב בטבלה
    ↓
המשבצות של התשובה מודגשות בגריד
    ↓
אותיות מופיעות אחת אחת (כ... ל... ב...)
    ↓
ההגדרה מסומנת כפתורה (✅ ירוק) בטבלה
    ↓
עוברים להגדרה הבאה...
    ↓
סיום - הצגת סיכום
```

### תרחיש עם התערבות ידנית
```
המשתמש לוחץ "▶ התחל פתרון"
    ↓
הפתרון רץ אוטומטית...
    ↓
המשתמש רואה טעות / רוצה להתערב
    ↓
המשתמש לוחץ "⏸ עצור"
    ↓
הפתרון נעצר - המערכת במצב המתנה
    ↓
המשתמש לוחץ על משבצת בגריד או על הגדרה בטבלה
    ↓
נפתח שדה קלט - המשתמש כותב תשובה
    ↓
התשובה מסומנת כ"🔒 ידנית" (נעולה)
    ↓
המשתמש לוחץ "▶ המשך"
    ↓
המערכת ממשיכה - מתייחסת לתשובות הידניות כאילוצים קבועים
```

---

## 3. ארכיטקטורה

### מבנה המסך

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Header: "פותר תשבץ - 45% הושלם"                                        │
│  [▶ התחל] [⏸ עצור] [↻ אפס]                              זמן: 00:32     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │                         │    │  טבלת הגדרות                        │ │
│  │      גריד התשבץ         │    │  ┌────┬─────────┬───────┬─────────┐ │ │
│  │                         │    │  │ # │ הגדרה   │ תשובה │ סטטוס   │ │ │
│  │  ┌───┬───┬───┬───┬───┐  │    │  ├────┼─────────┼───────┼─────────┤ │ │
│  │  │ כ │ ל │ ב │   │   │  │    │  │ 1 │בעל חיים │  כלב  │ ✅      │ │ │
│  │  ├───┼───┼───┼───┼───┤  │    │  │ 2 │ עיר     │  תל.. │ 🔄      │ │ │
│  │  │   │ ו │   │ ש │ ר │  │    │  │ 3 │ פרי     │  תפוח │ 🔒 ידני │ │ │
│  │  ├───┼───┼───┼───┼───┤  │    │  │ 4 │ צבע     │       │ ⏳      │ │ │
│  │  │   │ ט │   │   │   │  │    │  └────┴─────────┴───────┴─────────┘ │ │
│  │  ├───┼───┼───┼───┼───┤  │    │                                     │ │
│  │  │   │ ב │   │   │   │  │    │  ┌─────────────────────────────────┐ │ │
│  │  └───┴───┴───┴───┴───┘  │    │  │ עריכה ידנית:                   │ │ │
│  │                         │    │  │ הגדרה: "פרי אדום"              │ │ │
│  │  לחץ על משבצת לעריכה   │    │  │ תשובה: [תפוח____] [✓ שמור]    │ │ │
│  └─────────────────────────┘    │  └─────────────────────────────────┘ │ │
│                                 │                                     │ │
│                                 │  [סטטיסטיקות]                       │ │
│                                 │  נפתרו: 12/45 | ידניים: 3          │ │
│                                 │  Backtracks: 2 | ביטחון: 87%       │ │
│                                 └─────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### רכיבי UI

#### 3.1 סרגל בקרה (ControlBar)
```python
class ControlBar:
    """כפתורי שליטה בפתרון"""

    כפתורים:
    - [▶ התחל] - מתחיל פתרון חדש
    - [⏸ עצור] - עוצר את הפתרון (מאפשר עריכה)
    - [▶ המשך] - ממשיך אחרי עצירה
    - [↻ אפס] - מאפס הכל ומתחיל מחדש

    מצבים:
    - IDLE: מציג [▶ התחל]
    - RUNNING: מציג [⏸ עצור]
    - PAUSED: מציג [▶ המשך] + [↻ אפס]
    - COMPLETED: מציג [↻ אפס] + [💾 שמור]
```

#### 3.2 גריד התשבץ (CrosswordGrid)
```python
class CrosswordGridDisplay:
    """תצוגת גריד אינטראקטיבית עם תמיכה בעריכה"""

    סוגי משבצות:
    - BLOCK = רקע שחור
    - CLUE = רקע אפור עם טקסט קטן
    - SOLUTION:
        - ריקה = רקע לבן
        - בתהליך = רקע צהוב + אות מהבהבת
        - פתורה אוטומטית = רקע ירוק בהיר
        - פתורה ידנית = רקע כחול בהיר + 🔒
        - קונפליקט = רקע אדום

    אינטראקציה:
    - לחיצה על משבצת SOLUTION (במצב PAUSED) → פותח עריכה
    - הדגשה של כל המשבצות של אותה הגדרה בהובר
```

#### 3.3 טבלת הגדרות (CluesTable)
```python
class CluesTableDisplay:
    """טבלה דינמית עם תמיכה בעריכה"""

    עמודות:
    - # (מספר סידורי)
    - הגדרה (טקסט)
    - תשובה (מתמלאת בזמן אמת / ניתנת לעריכה)
    - סטטוס (אייקון)

    סטטוסים:
    - ⏳ ממתין (pending)
    - 🔄 בתהליך (in_progress) - שורה צהובה
    - ✅ נפתר אוטומטית (solved) - שורה ירוקה
    - 🔒 הוכנס ידנית (manual) - שורה כחולה
    - ❌ נכשל (failed) - שורה אדומה
    - ↩️ Backtrack - שורה כתומה

    אינטראקציה:
    - לחיצה על שורה (במצב PAUSED) → בחירה לעריכה
    - השורה הנבחרת מודגשת + מופיע שדה עריכה
```

#### 3.4 פאנל עריכה ידנית (ManualEditPanel)
```python
class ManualEditPanel:
    """פאנל לעריכת תשובות ידנית"""

    מוצג רק במצב PAUSED כשנבחרה הגדרה

    מציג:
    - טקסט ההגדרה
    - אורך התשובה הנדרש
    - אותיות ידועות (מהצלבות)
    - שדה קלט לתשובה
    - [✓ שמור] [✗ בטל]

    וולידציה:
    - אורך התשובה חייב להיות תואם
    - אותיות ידועות חייבות להתאים
    - אם לא תואם → הודעת שגיאה
```

#### 3.5 פאנל סטטיסטיקות (StatsPanel)
```python
class StatsPanel:
    """סטטיסטיקות בזמן אמת"""

    מציג:
    - Progress bar עם אחוזים
    - שעון (זמן שעבר)
    - נפתרו: X/Y
    - הוכנסו ידנית: Z
    - Backtracks: N
    - ביטחון ממוצע: XX%
```

---

## 4. זרימת נתונים

### State Management

```python
@dataclass
class SolverUIState:
    """מצב ה-UI בזמן פתרון"""

    # מצב כללי
    mode: SolverMode = SolverMode.IDLE  # IDLE / RUNNING / PAUSED / COMPLETED
    selected_clue_id: Optional[str] = None  # הגדרה שנבחרה לעריכה

    # התקדמות
    total_clues: int = 0
    solved_clues: int = 0
    manual_clues: int = 0  # כמה הוכנסו ידנית
    current_clue_id: Optional[str] = None

    # גריד
    grid_letters: Dict[Tuple[int,int], str] = {}  # (row,col) -> letter
    highlighted_cells: List[Tuple[int,int]] = []  # משבצות מודגשות
    manual_cells: Set[Tuple[int,int]] = set()     # משבצות עם תשובה ידנית
    conflict_cells: List[Tuple[int,int]] = []     # משבצות עם קונפליקט

    # הגדרות
    clue_statuses: Dict[str, ClueStatus] = {}     # clue_id -> status
    clue_answers: Dict[str, str] = {}             # clue_id -> answer
    manual_clue_ids: Set[str] = set()             # הגדרות שהוכנסו ידנית

    # סטטיסטיקות
    start_time: float = 0
    backtracks: int = 0
    avg_confidence: float = 0


class SolverMode(Enum):
    IDLE = "idle"           # לא התחיל
    RUNNING = "running"     # רץ אוטומטית
    PAUSED = "paused"       # עצור - מאפשר עריכה
    COMPLETED = "completed" # סיים


class ClueStatus(Enum):
    PENDING = "pending"         # ⏳ ממתין
    IN_PROGRESS = "in_progress" # 🔄 בתהליך
    SOLVED = "solved"           # ✅ נפתר אוטומטית
    MANUAL = "manual"           # 🔒 הוכנס ידנית
    FAILED = "failed"           # ❌ נכשל
    BACKTRACKED = "backtracked" # ↩️ בוטל
```

### Event System

```python
class SolverEvent:
    """אירועים מהפותר ל-UI"""

    # אירועי פתרון
    CLUE_STARTED = "clue_started"      # התחלת פתרון הגדרה
    LETTER_PLACED = "letter_placed"    # שיבוץ אות בודדת
    CLUE_SOLVED = "clue_solved"        # הגדרה נפתרה
    CLUE_FAILED = "clue_failed"        # הגדרה נכשלה
    BACKTRACK = "backtrack"            # חזרה אחורה
    CONFLICT = "conflict"              # זוהה קונפליקט
    COMPLETED = "completed"            # הפתרון הסתיים

    # אירועי עריכה ידנית
    MANUAL_ENTRY = "manual_entry"      # המשתמש הכניס תשובה
    MANUAL_CLEARED = "manual_cleared"  # המשתמש מחק תשובה ידנית
```

### Callback Flow - פתרון אוטומטי

```
PuzzleSolver.solve()
    │
    ├── on_clue_start(clue_id, cells)
    │       UI: הדגש שורה בטבלה + משבצות בגריד
    │
    ├── [לכל אות בתשובה]
    │   └── on_letter_placed(row, col, letter, index)
    │           UI: הוסף אות בגריד עם אנימציה
    │           UI: המתן 100-200ms (לאפקט ויזואלי)
    │
    ├── on_clue_solved(clue_id, answer, confidence)
    │       UI: סמן שורה כ-✅
    │       UI: הסר הדגשה מהמשבצות
    │       UI: עדכן סטטיסטיקות
    │
    ├── on_backtrack(clue_id, removed_letters)
    │       UI: סמן שורה כ-↩️
    │       UI: הסר אותיות מהגריד (אנימציית fade-out)
    │       UI: עדכן מונה backtracks
    │
    └── on_completed(stats)
            UI: הצג סיכום
            UI: שנה מצב ל-COMPLETED
```

### Callback Flow - עריכה ידנית

```
User clicks [⏸ עצור]
    │
    └── UI: שנה מצב ל-PAUSED, הפעל אפשרות עריכה

User clicks on clue row / grid cell
    │
    └── UI: בחר הגדרה, הצג ManualEditPanel

User enters answer and clicks [✓ שמור]
    │
    ├── Validate:
    │   ├── אורך תשובה == אורך נדרש?
    │   └── אותיות ידועות תואמות?
    │
    ├── [אם תקין]
    │   ├── UI: הוסף אותיות לגריד
    │   ├── UI: סמן משבצות ככחולות (ידני)
    │   ├── UI: סמן שורה כ-🔒
    │   ├── State: הוסף ל-manual_clue_ids
    │   └── Solver: עדכן known_letters להגדרות אחרות
    │
    └── [אם לא תקין]
        └── UI: הצג הודעת שגיאה

User clicks [▶ המשך]
    │
    ├── Solver: קבל את התשובות הידניות כאילוצים קבועים
    │           (לא לגעת בהם, לא לעשות להם backtrack)
    │
    └── UI: שנה מצב ל-RUNNING, המשך פתרון
```

---

## 5. לוגיקת אילוצים ידניים

### עקרון מרכזי
> **תשובות שהוכנסו ידנית הן "אמת מוחלטת".**
> המערכת מתייחסת אליהן כאילוצים שלא ניתן לשנות.

### יישום ב-PuzzleSolver

```python
class PuzzleSolver:
    def __init__(self, ...):
        self.manual_answers: Dict[str, str] = {}  # clue_id -> answer
        self.locked_cells: Set[Tuple[int,int]] = set()  # משבצות נעולות

    def set_manual_answer(self, clue: ClueEntry, answer: str):
        """הגדרת תשובה ידנית - הופכת לאילוץ קבוע"""
        self.manual_answers[clue.id] = answer
        self.locked_cells.update(clue.answer_cells)

        # עדכון אותיות ידועות להגדרות מצטלבות
        self._propagate_known_letters(clue, answer)

    def _can_backtrack_clue(self, clue: ClueEntry) -> bool:
        """בדיקה אם אפשר לעשות backtrack להגדרה"""
        # אי אפשר לעשות backtrack לתשובה ידנית!
        return clue.id not in self.manual_answers

    def _is_cell_locked(self, row: int, col: int) -> bool:
        """בדיקה אם משבצת נעולה (חלק מתשובה ידנית)"""
        return (row, col) in self.locked_cells

    def solve(self, ...):
        # בהתחלה - שבץ את כל התשובות הידניות
        for clue_id, answer in self.manual_answers.items():
            clue = self.clue_db.get_clue(clue_id)
            self.solution.place_answer(clue, answer, confidence=1.0)

        # המשך פתרון רגיל, אבל:
        # 1. דלג על הגדרות שכבר הוכנסו ידנית
        # 2. אל תעשה backtrack לתשובות ידניות
        # 3. השתמש באותיות הידניות כאילוצים
```

### דוגמה

```
מצב: המשתמש הכניס ידנית "תפוח" להגדרה "פרי אדום"

      col 0   col 1   col 2   col 3   col 4
row 0  [  ]   [הגדרה]  [  ]    [  ]    [  ]
row 1  [  ]    [ת]🔒   [פ]🔒   [ו]🔒   [ח]🔒

המשבצות (1,1), (1,2), (1,3), (1,4) נעולות.

עכשיו יש הגדרה אחרת שמצטלבת ב-(1,2):
- ההגדרה יודעת שבמיקום 0 יש "פ"
- היא תחפש תשובות שמתחילות ב-"פ"
- אם אין התאמה → המערכת נכשלת (לא משנה את הידני)
```

---

## 6. דגשים טכניים

### 6.1 ביצועים
- עדכון אות בודדת: `st.empty()` + החלפת HTML
- לא לרנדר את כל הגריד בכל עדכון
- השהיה של 100-200ms בין אותיות (לאפקט ויזואלי)

### 6.2 Streamlit State
```python
# Session state keys
st.session_state['solver_ui_state'] = SolverUIState()
st.session_state['solver_instance'] = None
st.session_state['is_solving'] = False
```

### 6.3 עיצוב

```python
CELL_COLORS = {
    'block': '#000000',       # שחור
    'clue': '#E0E0E0',        # אפור
    'empty': '#FFFFFF',       # לבן
    'solving': '#FFEB3B',     # צהוב
    'solved': '#C8E6C9',      # ירוק בהיר
    'manual': '#BBDEFB',      # כחול בהיר
    'conflict': '#FFCDD2',    # אדום בהיר
    'locked_border': '#1976D2' # כחול כהה (גבול למשבצת נעולה)
}
```

### 6.4 אנימציות
- **הופעת אות:** fade-in 0.2s
- **הדגשת משבצת בתהליך:** pulse animation
- **Backtrack:** fade-out 0.3s עם צבע אדום
- **נעילה ידנית:** border pulse כחול

### 6.5 תאימות RTL
- הגריד והטבלה ב-RTL
- כיוון הכתיבה בשדות קלט: RTL
- מספור מימין לשמאל

---

## 7. תוכנית יישום

### שלב 1: עדכון PuzzleSolver
**קובץ:** `services/puzzle_solver.py`

- הוספת callbacks לכל אות (לא רק לכל מילה)
- הוספת תמיכה ב-manual_answers
- הוספת locked_cells
- שינוי לוגיקת backtrack

### שלב 2: יצירת State ו-Events
**קובץ חדש:** `ui/solver_state.py`

- SolverUIState dataclass
- SolverMode enum
- ClueStatus enum
- SolverEvent enum

### שלב 3: רכיבי UI
**קבצים חדשים:**
- `ui/control_bar.py` - כפתורי שליטה
- `ui/crossword_grid.py` - גריד אינטראקטיבי
- `ui/clues_table.py` - טבלה עם עריכה
- `ui/manual_edit_panel.py` - פאנל עריכה
- `ui/stats_panel.py` - סטטיסטיקות
- `ui/solver_view.py` - הרכבת הכל

### שלב 4: אינטגרציה
**קובץ:** `app.py`

- הוספת Phase 4 עם SolverView
- חיבור ל-session_state

### שלב 5: CSS
**קובץ:** `static/solver_styles.css`

- עיצוב כל הרכיבים
- אנימציות
- RTL

---

## 8. מבנה קבצים

```
crossword_solver/
├── ui/                              # תיקייה חדשה
│   ├── __init__.py
│   ├── solver_state.py             # State + Enums
│   ├── control_bar.py              # כפתורי שליטה
│   ├── crossword_grid.py           # גריד אינטראקטיבי
│   ├── clues_table.py              # טבלת הגדרות
│   ├── manual_edit_panel.py        # פאנל עריכה ידנית
│   ├── stats_panel.py              # סטטיסטיקות
│   └── solver_view.py              # View מרכזי
│
├── static/                          # תיקייה חדשה
│   └── solver_styles.css           # עיצוב
│
├── services/
│   └── puzzle_solver.py            # עדכון עם callbacks + manual support
│
└── app.py                           # אינטגרציה
```

---

## 9. סיכום

### מה המשתמש מקבל:
1. **צפייה מרתקת** - רואה את התשבץ נפתר אות אחר אות
2. **שליטה מלאה** - יכול לעצור בכל רגע
3. **התערבות ידנית** - יכול לתקן או להוסיף תשובות
4. **אמינות** - תשובות ידניות נשמרות ולא נמחקות

### עקרונות מרכזיים:
- כל אות מופיעה בנפרד (לא מילה שלמה)
- תשובות ידניות = אילוצים קבועים
- המערכת לא יכולה לשנות תשובה ידנית
- Backtrack לא נוגע בתשובות ידניות
