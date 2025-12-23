# models/grid.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

# --- Enums: הגדרת הקבועים ---

class CellType(Enum):
    BLOCK = "BLOCK"           # משבצת שחורה אטומה
    SOLUTION = "SOLUTION"     # משבצת לבנה (מיועדת לכתיבת אות)
    CLUE = "CLUE"             # משבצת הגדרה

class SplitType(Enum):
    NONE = "NONE"             # משבצת הגדרה רגילה (לא חצויה)
    HORIZONTAL = "HORIZONTAL" # קו מפריד לרוחב (הגדרה עליונה / תחתונה)
    VERTICAL = "VERTICAL"     # קו מפריד לאורך (הגדרה ימנית / שמאלית)

class ArrowDirection(Enum):
    # כיוונים ראשיים
    NONE = "NONE"
    DOWN = "DOWN"             # חץ ישר למטה
    UP = "UP"                 # חץ ישר למעלה
    LEFT = "LEFT"             # חץ ישר שמאלה
    RIGHT = "RIGHT"           # חץ ישר ימינה
    
    # כיוונים מורכבים (מדרגות/פינות)
    # הפורמט: STEP_[DIRECTION1]_[DIRECTION2]
    
    # מתחיל שמאלה
    STEP_LEFT_DOWN = "STEP_LEFT_DOWN"   # שמאלה ואז למטה
    STEP_LEFT_UP = "STEP_LEFT_UP"       # שמאלה ואז למעלה
    
    # מתחיל למטה
    STEP_DOWN_LEFT = "STEP_DOWN_LEFT"   # למטה ואז שמאלה
    STEP_DOWN_RIGHT = "STEP_DOWN_RIGHT" # למטה ואז ימינה
    
    # מתחיל למעלה
    STEP_UP_RIGHT = "STEP_UP_RIGHT"     # למעלה ואז ימינה
    STEP_UP_LEFT = "STEP_UP_LEFT"       # למעלה ואז שמאלה
    
    # מתחיל ימינה
    STEP_RIGHT_UP = "STEP_RIGHT_UP"     # ימינה ואז למעלה
    STEP_RIGHT_DOWN = "STEP_RIGHT_DOWN" # ימינה ואז למטה

# --- שכבה 1: המידע הגולמי (משבצת הגדרה) ---

@dataclass
class ClueMeta:
    """מייצג הגדרה בודדת בתוך משבצת (יכול להיות 1 או 2 במשבצת)"""
    id: str                   # מזהה ייחודי (למשל: "clue_3_4_top")
    raw_text: str = ""        # הטקסט שה-LLM זיהה (ההגדרה עצמה)
    direction: ArrowDirection = ArrowDirection.NONE # לאן החץ מצביע
    
    # מיקום יחסי בתוך המשבצת (עבור חצויות)
    # top/bottom עבור חלוקה אופקית (HORIZONTAL)
    # right/left עבור חלוקה אנכית (VERTICAL)
    # full עבור משבצת לא חצויה
    sub_position: str = "full" 

# --- שכבה 2: הגריד הפיזי (המטריצה) ---

@dataclass
class Cell:
    """האטום הבסיסי של המטריצה"""
    row: int
    col: int
    type: CellType = CellType.SOLUTION # ברירת מחדל
    
    # רלוונטי רק אם type == SOLUTION
    current_val: str = ""     # האות שהמערכת הציבה כרגע (ריק בהתחלה)
    
    # רלוונטי רק אם type == CLUE
    split_type: SplitType = SplitType.NONE
    clues: List[ClueMeta] = field(default_factory=list) # רשימת ההגדרות במשבצת

@dataclass
class GridMatrix:
    rows: int
    cols: int
    matrix: List[List[Cell]] = field(default_factory=list)

    def initialize_grid(self):
        """מאתחל מטריצה ריקה של תאים"""
        self.matrix = [
            [Cell(row=r, col=c) for c in range(self.cols)]
            for r in range(self.rows)
        ]

# --- שכבה 3: הגריד הלוגי (רשימת המשימות לפתרון) ---

@dataclass
class WordSlot:
    """מייצג 'מילה' שצריך למצוא לה פתרון"""
    clue_id: str              # מצביע ל-ClueMeta הרלוונטי
    definition_text: str      # הטקסט של ההגדרה (משוכפל לנוחות)
    length: int               # אורך המילה (מחושב ע"י המערכת)
    
    # רשימת הקואורדינטות של המשבצות הלבנות שמרכיבות את המילה
    # סדר הרשימה הוא סדר האותיות במילה
    cells_coordinates: List[Tuple[int, int]] 

    # האילוצים הידועים כרגע (למשל: אות שנייה חייבת להיות 'א')
    # המפתח הוא האינדקס במילה (0, 1...), הערך הוא האות המחייבת
    current_constraints: dict = field(default_factory=dict)