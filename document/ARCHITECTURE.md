# Crossword Solver - Architecture Documentation

## Overview

מערכת לפתרון תשבצים עבריים באמצעות ראייה ממוחשבת ו-AI.

---

## Data Flow - זרימת הנתונים

```
┌─────────────────┐
│   תמונת תשבץ    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1: Grid Detection (VisionService)                │
│  - זיהוי קווי הגריד                                     │
│  - סיווג משבצות: BLOCK / CLUE / SOLUTION               │
│  - יצירת GridMatrix                                     │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2: Recognition (BatchProcessor)                  │
│  - לכל משבצת CLUE:                                      │
│    ├── Google Vision → טקסט ההגדרה                     │
│    └── Claude Vision → זיהוי חצים (1 או 2)             │
│  - אם 2 חצים → קריאה נוספת לקלוד לפיצול טקסט          │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 3: ClueDatabase (עתידי)                          │
│  - בניית רשימת הגדרות מלאה                              │
│  - חישוב אורך תשובה לכל הגדרה                           │
│  - זיהוי הצלבות                                         │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 4: Solving (עתידי)                               │
│  - קבלת תשובות אפשריות מ-LLM                           │
│  - אלגוריתם שיבוץ (Constraint Satisfaction)            │
│  - Backtracking                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Data Structures - מבני נתונים

### Layer 1: GridMatrix (Physical Grid)

**קובץ:** `models/grid.py`

```python
@dataclass
class Cell:
    row: int
    col: int
    type: CellType  # BLOCK / CLUE / SOLUTION
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2) מיקום בתמונה

    # עבור CLUE cells:
    split_type: SplitType  # NONE / HORIZONTAL / VERTICAL
    clues: List[ClueMeta]  # מידע גולמי על ההגדרות

    # עבור SOLUTION cells:
    current_val: str  # האות שתיכתב (ריק בהתחלה)

    # נתונים מעובדים (מתווספים ב-BatchProcessor):
    parsed_clues: List[dict]  # תוצאות OCR + חצים
    debug_image: bytes  # תמונה ל-OCR
    arrow_debug_image: bytes  # תמונה לחצים

@dataclass
class GridMatrix:
    rows: int
    cols: int
    matrix: List[List[Cell]]
```

**איפה יושב:** `st.session_state.grid_obj`

---

### Layer 2: ClueDatabase (Logical Clues) - מומש!

**קובץ:** `models/clue_entry.py`

```python
@dataclass
class ClueEntry:
    # זיהוי
    id: str  # "clue_0_0_full" או "clue_0_0_top"
    source_cell: Tuple[int, int]  # (row, col)
    zone: str  # "full" / "top" / "bottom" / "left" / "right"

    # תוכן
    text: str  # טקסט ההגדרה ("בעל חיים")

    # חץ
    arrow_direction: str  # "down" / "right" / "down-right" וכו'
    arrow_position: str  # "top-right" / "bottom-left"
    arrow_confidence: float

    # מיקום התשובה (מחושב)
    answer_start_cell: Tuple[int, int]  # היכן מתחילה התשובה
    writing_direction: str  # "down" / "right" / "left" / "up"
    answer_length: int  # כמה אותיות
    answer_cells: List[Tuple[int, int]]  # כל המשבצות של התשובה

    # פתרון
    known_letters: Dict[int, str]  # אותיות ידועות מהצלבות {0: 'כ', 2: 'ב'}
    candidates: List[str]  # תשובות אפשריות ["כלב", "כלבה"]
    chosen_answer: Optional[str]  # התשובה שנבחרה

    # מטא
    ocr_confidence: float
    overall_confidence: float
```

**איפה יישב:** `st.session_state.clue_database` (רשימה של ClueEntry)

---

### Layer 3: SolutionGrid - מומש!

**קובץ:** `services/solution_grid.py`

```python
@dataclass
class SolutionCell:
    letter: str  # האות שהוכנסה
    confidence: float
    source_clues: List[str]  # אילו הגדרות עוברות פה
    is_conflict: bool  # האם יש סתירה

class SolutionGrid:
    def __init__(self, rows: int, cols: int):
        self.grid: List[List[Optional[SolutionCell]]]

    def place_answer(self, clue: ClueEntry, answer: str) -> bool:
        """מנסה לשבץ תשובה, מחזיר האם הצליח"""
        pass

    def check_conflicts(self) -> List[Tuple[int, int]]:
        """מחזיר רשימת משבצות עם סתירות"""
        pass

    def get_known_letters(self, cells: List[Tuple[int, int]]) -> Dict[int, str]:
        """מחזיר אותיות ידועות עבור רשימת משבצות"""
        pass
```

---

## Services Architecture

### Current Services (Phase 2)

```
services/
├── vision_service.py          # זיהוי גריד וסיווג משבצות
├── ocr_service_new.py         # תיאום OCR (entry point)
├── recognition_orchestrator.py # תיאום Google Vision + Claude
├── batch_processor.py         # עיבוד כל המשבצות
├── google_vision_ocr.py       # OCR עם Google Cloud Vision
├── claude_arrow_detector.py   # זיהוי חצים עם Claude
└── confidence_scorer.py       # חישוב ציוני ביטחון
```

### Phase 3-4 Services - מומש!

```
services/
├── arrow_offset_calculator.py  # חישוב מיקום תחילת תשובה ✅
├── clue_database.py           # ניהול ה-ClueDatabase ✅
├── split_cell_analyzer.py     # ניתוח משבצות חצויות (Claude) ✅
├── solution_grid.py           # מטריצת הפתרון ✅
├── clue_solver.py             # קבלת תשובות מ-LLM ✅
└── puzzle_solver.py           # אלגוריתם השיבוץ ✅
```

---

## Split Cell Logic - לוגיקה למשבצות חצויות

### הזרימה המעודכנת:

```
משבצת CLUE
    │
    ├── Google Vision → טקסט מלא
    │
    └── Claude → זיהוי חצים
            │
            ├── 0-1 חצים → משבצת רגילה
            │       └── שמירה רגילה ב-parsed_clues
            │
            └── 2 חצים → משבצת חצויה!
                    │
                    └── קריאה נוספת לקלוד:
                        "זו משבצת חצויה. פצל את הטקסט
                         בין 2 ההגדרות ושייך כל חץ להגדרה"
                            │
                            ▼
                        {
                          "definitions": [
                            {"text": "הגדרה 1", "arrow": "down"},
                            {"text": "הגדרה 2", "arrow": "right"}
                          ]
                        }
```

### פרומפט לניתוח משבצת חצויה:

```
You are analyzing a SPLIT crossword clue cell that contains TWO separate definitions.

Context:
- This cell has 2 arrows pointing in different directions
- Each arrow belongs to a different definition
- The cell is visually divided (horizontally or vertically)

Full text detected by OCR: "{ocr_text}"
Arrows detected: {arrows}

Task: Split the text into the two definitions and match each to its arrow.

Respond with JSON:
{
  "definitions": [
    {
      "text": "first definition text",
      "arrow_direction": "down",
      "position": "top"  // where this definition appears in the cell
    },
    {
      "text": "second definition text",
      "arrow_direction": "right",
      "position": "bottom"
    }
  ]
}
```

---

## Arrow Offset Logic - חישוב אופסט

### הכלל המרכזי:
> **האופסט נקבע לפי הכיוון הראשון של החץ.**
> **כיוון הכתיבה נקבע לפי הכיוון השני של החץ.**

### טבלת המרה מלאה (מתוקנת):

| Arrow Direction | Offset (row, col) | Writing Direction |
|-----------------|-------------------|-------------------|
| `down` | (+1, 0) | down |
| `up` | (-1, 0) | up |
| `right` | (0, +1) | right |
| `left` | (0, -1) | left |
| `down-right` | **(+1, 0)** | right |
| `down-left` | **(+1, 0)** | left |
| `up-right` | **(-1, 0)** | right |
| `up-left` | **(-1, 0)** | left |
| `right-down` | **(0, +1)** | down |
| `right-up` | **(0, +1)** | up |
| `left-down` | **(0, -1)** | down |
| `left-up` | **(0, -1)** | up |

### דוגמה:

```
משבצת הגדרה במיקום (2, 3) עם חץ "down-right"
    │
    ├── Offset: (+1, 0)  ← לפי הכיוון הראשון (down)
    │   → התשובה מתחילה במשבצת (3, 3)
    │
    └── Writing Direction: "right"  ← לפי הכיוון השני
        → הולכים ימינה: (3,3), (3,4), (3,5)...
```

### איור ויזואלי:

```
חץ down-right:
         col 2   col 3   col 4
row 2    [  ]   [הגדרה]  [  ]
                  ↓→
row 3    [  ]   [תחילה]→ [  ] → [  ]
```

---

## API Usage & Costs

### Google Cloud Vision
- **שימוש:** OCR לכל משבצת CLUE
- **עלות:** ~$1.50 / 1000 תמונות
- **קריאות לתשבץ:** ~20-50 (לפי מספר משבצות CLUE)

### Claude (Anthropic)
- **שימוש:**
  1. זיהוי חצים לכל משבצת CLUE
  2. פיצול טקסט למשבצות חצויות (רק אם 2 חצים)
  3. פתרון הגדרות (Phase 4)
- **עלות:** ~$0.003 / תמונה (Haiku)
- **קריאות לתשבץ:** ~20-50 (חצים) + ~5-10 (חצויות) + ~50 (פתרון)

---

## File Structure

```
crossword_solver/
├── app.py                     # Streamlit UI
├── requirements.txt
├── ROADMAP.md
│
├── models/
│   ├── grid.py               # Cell, GridMatrix, CellType, etc.
│   ├── recognition_result.py # OcrResult, ArrowResult, etc.
│   └── clue_entry.py         # ClueEntry ✅
│
├── services/
│   ├── vision_service.py     # Grid detection
│   ├── ocr_service_new.py    # OCR coordination
│   ├── recognition_orchestrator.py
│   ├── batch_processor.py
│   ├── google_vision_ocr.py
│   ├── claude_arrow_detector.py
│   ├── confidence_scorer.py
│   ├── arrow_offset_calculator.py  # חישוב אופסט חץ ✅
│   ├── split_cell_analyzer.py      # ניתוח משבצות חצויות ✅
│   ├── clue_database.py            # ניהול הגדרות ✅
│   ├── solution_grid.py            # מטריצת פתרון ✅
│   ├── clue_solver.py              # פתרון הגדרות עם LLM ✅
│   └── puzzle_solver.py            # אלגוריתם שיבוץ ✅
│
├── config/
│   └── cloud_config.py       # API keys configuration
│
├── docs/
│   └── ARCHITECTURE.md       # This file
│
└── templates/                # Arrow templates (legacy)
```

---

## State Management

### Streamlit Session State

```python
st.session_state = {
    # Grid data
    'grid_obj': GridMatrix,           # המטריצה הפיזית
    'original_image': np.ndarray,     # התמונה המקורית
    'preview_image': np.ndarray,      # תמונה עם הגריד מסומן

    # Recognition results (Phase 2)
    'recognition_done': bool,

    # Clue database (Phase 3 - עתידי)
    'clue_database': List[ClueEntry],

    # Solution (Phase 4 - עתידי)
    'solution_grid': SolutionGrid,
    'solving_in_progress': bool,
}
```

---

## Implementation Status

### Phase 3: Data Structure & Split Cells - מומש!
- [x] `models/clue_entry.py` - מודל ההגדרה
- [x] `services/arrow_offset_calculator.py` - חישוב אופסט
- [x] `services/split_cell_analyzer.py` - ניתוח משבצות חצויות
- [x] `services/clue_database.py` - ניהול הגדרות (כולל חישוב אורך והצלבות)

### Phase 4: Solving Algorithm - מומש!
- [x] `services/clue_solver.py` - קבלת תשובות מקלוד
- [x] `services/solution_grid.py` - מטריצת פתרון
- [x] `services/puzzle_solver.py` - אלגוריתם שיבוץ עם Backtracking

### Next Steps: Integration & UI
1. [ ] אינטגרציה של ClueDatabase ב-app.py
2. [ ] UI לשלב הפתרון
3. [ ] תצוגת פתרון בגריד
4. [ ] עריכה ידנית
5. [ ] ייצוא תוצאות

---

## Quick Reference - How to Use

### Building ClueDatabase from Grid:
```python
from services.clue_database import ClueDatabase

clue_db = ClueDatabase()
clue_db.build_from_grid(grid_obj)  # grid_obj מ-VisionService

# קבלת סטטיסטיקות
stats = clue_db.get_statistics()
print(f"Total clues: {stats['total_clues']}")
print(f"With answer length: {stats['with_answer_length']}")
```

### Solving the Puzzle:
```python
from services.solution_grid import SolutionGrid
from services.clue_solver import ClueSolver
from services.puzzle_solver import PuzzleSolver

# יצירת components
solution = SolutionGrid(grid_obj.rows, grid_obj.cols)
solver = ClueSolver(api_key=claude_api_key)
puzzle_solver = PuzzleSolver(clue_db, solution, solver)

# פתרון
def on_progress(progress):
    print(f"Solved: {progress.solved_clues}/{progress.total_clues}")

result = puzzle_solver.solve(progress_callback=on_progress)

# תוצאות
print(solution.to_string_grid())
print(puzzle_solver.get_statistics())
```

### Manual Placement:
```python
clue = clue_db.get_clue("clue_0_0_full")
puzzle_solver.manual_place(clue, "כלב")
```

### Getting a Hint:
```python
hint = puzzle_solver.get_hint(clue)
if hint:
    answer, confidence = hint
    print(f"Hint: {answer} ({confidence:.0%})")
```
