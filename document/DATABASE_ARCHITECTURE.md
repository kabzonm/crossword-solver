# תכנון מערכת Database לשמירת תשבצים

## רקע ומוטיבציה

### הבעיה
כל הרצה של זיהוי תשבץ עם Gemini כרוכה בעלויות גבוהות:
- שליחת תמונות ל-API
- עיבוד עם מודל Vision
- תשלום לפי tokens

### הפתרון המוצע
מעבר ממצב שנשמר ב-session_state (נמחק בסגירת הדפדפן) למצב שנשמר ב-Database קבוע.

---

## 1. ביקורת בונה על הרעיון

### יתרונות
1. **חיסכון בעלויות** - סריקה חד-פעמית לכל תשבץ
2. **פיתוח מהיר** - עבודה על מנוע הפתרון בלי לחכות לסריקה
3. **גיבוי** - לא מאבדים עבודה אם הדפדפן נסגר
4. **שיתוף** - אפשר לייצא/לייבא תשבצים (בעתיד)
5. **סטטיסטיקות** - מעקב אחרי תשבצים שנפתרו

### חסרונות ואתגרים
1. **סנכרון** - צריך לוודא שהנתונים ב-DB תואמים למבנה בקוד
2. **מיגרציות** - אם מבנה הנתונים ישתנה, צריך לעדכן DB ישנים
3. **גודל קבצים** - תמונות תופסות מקום (אפשר לדחוס)
4. **תחזוקה** - עוד שכבה לנהל

### המלצות לשיפור
1. **גרסאות** - לשמור version של המבנה, להתמודד עם שינויים
2. **דחיסת תמונות** - לשמור JPEG בלבד, לא numpy arrays
3. **אינדקסים** - לבנות אינדקסים נכונים לחיפוש מהיר
4. **ייצוא** - לאפשר export ל-JSON לגיבוי/שיתוף

---

## 2. השוואת טכנולוגיות Database

### אופציה א': SQLite

| קריטריון | ערך |
|----------|-----|
| התקנה | לא נדרשת - מובנה ב-Python |
| קובץ | קובץ `.db` יחיד |
| מורכבות | פשוט מאוד |
| ביצועים | מעולה לשימוש מקומי |
| גיבוי | פשוט להעתיק קובץ |
| תמונות | Binary BLOBs |
| מתאים ל | פרויקט יחיד, משתמש יחיד |

**יתרונות:**
- Zero configuration
- קובץ יחיד - קל להעביר/לגבות
- מהיר מאוד לקריאה/כתיבה מקומית
- תמיכה מלאה ב-SQL
- מובנה ב-Python (sqlite3)

**חסרונות:**
- לא מתאים למספר משתמשים בו-זמנית
- אין שרת (לא מתאים לענן בלי עבודה נוספת)

### אופציה ב': PostgreSQL

| קריטריון | ערך |
|----------|-----|
| התקנה | צריך להתקין שרת |
| קובץ | שרת + connection string |
| מורכבות | בינונית |
| ביצועים | מעולה, גם ל-concurrent |
| גיבוי | דורש pg_dump |
| תמונות | bytea או קבצים נפרדים |
| מתאים ל | פרויקט production, מספר משתמשים |

**יתרונות:**
- מתאים ל-production
- תמיכה ב-concurrent access
- פיצ'רים מתקדמים (JSONB, full-text search)

**חסרונות:**
- צריך להתקין ולהריץ שרת
- יותר מורכב לתחזוקה
- overkill לפרויקט מקומי

### אופציה ג': JSON Files

| קריטריון | ערך |
|----------|-----|
| התקנה | לא נדרשת |
| קובץ | קובץ `.json` לכל תשבץ |
| מורכבות | פשוט ביותר |
| ביצועים | טוב לקריאה, בעייתי לעדכונים |
| גיבוי | פשוט |
| תמונות | Base64 או קבצים נפרדים |
| מתאים ל | MVP, ייצוא/ייבוא |

**יתרונות:**
- קריא לאדם
- קל לדבג
- אין תלויות

**חסרונות:**
- אין אינדקסים
- איטי לחיפוש
- Base64 מנפח תמונות x1.33

---

## 3. ההמלצה שלי: SQLite

### סיבות לבחירה:
1. **פשטות** - אין צורך להתקין כלום
2. **ניידות** - קובץ יחיד שקל להעביר
3. **ביצועים** - מספיק טוב לתשבצים (מאות, לא מיליונים)
4. **Python native** - מובנה, אין תלויות
5. **SQL** - שפה סטנדרטית, קל להרחיב

### מיקום הקובץ:
```
crossword_solver/
├── data/
│   └── crosswords.db    <-- כאן
├── app.py
└── ...
```

---

## 4. ארכיטקטורת ה-Database

### טבלאות

#### טבלה 1: `puzzles` (תשבצים)
```sql
CREATE TABLE puzzles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- שם התשבץ (מהמשתמש)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- מידע על הגריד
    rows INTEGER NOT NULL,
    cols INTEGER NOT NULL,

    -- התמונה המקורית (JPEG compressed)
    original_image BLOB,

    -- מטא-דאטה
    schema_version INTEGER DEFAULT 1     -- לטיפול במיגרציות עתידיות
);
```

#### טבלה 2: `cells` (משבצות)
```sql
CREATE TABLE cells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_id INTEGER NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,

    -- סוג התא
    cell_type TEXT NOT NULL,             -- 'BLOCK' / 'SOLUTION' / 'CLUE'

    -- תמונות דיבוג (JPEG compressed, nullable)
    debug_image BLOB,                    -- תמונת OCR
    arrow_debug_image BLOB,              -- תמונת חצים

    FOREIGN KEY (puzzle_id) REFERENCES puzzles(id) ON DELETE CASCADE,
    UNIQUE(puzzle_id, row, col)
);
```

#### טבלה 3: `clues` (הגדרות)
```sql
CREATE TABLE clues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_id INTEGER NOT NULL,
    cell_id INTEGER NOT NULL,

    -- מזהה ייחודי בפורמט "clue_row_col_zone"
    clue_id TEXT NOT NULL,

    -- תוכן
    text TEXT NOT NULL,                  -- טקסט ההגדרה
    zone TEXT DEFAULT 'full',            -- 'full' / 'top' / 'bottom' / 'left' / 'right'

    -- ביטחון
    confidence REAL DEFAULT 0.0,
    ocr_confidence REAL DEFAULT 0.0,
    arrow_confidence REAL DEFAULT 0.0,

    -- כיוון וחץ (מה-Gemini)
    arrow_direction TEXT,                -- 'straight-down', etc.
    arrow_position TEXT,
    exit_side TEXT,                      -- 'top' / 'bottom' / 'left' / 'right'
    arrowhead_direction TEXT,            -- 'up' / 'down' / 'left' / 'right'

    -- מיקום התשובה (מחושב)
    answer_start_row INTEGER,
    answer_start_col INTEGER,
    writing_direction TEXT,              -- 'down' / 'right' / 'up' / 'left'
    answer_length INTEGER DEFAULT 0,

    FOREIGN KEY (puzzle_id) REFERENCES puzzles(id) ON DELETE CASCADE,
    FOREIGN KEY (cell_id) REFERENCES cells(id) ON DELETE CASCADE,
    UNIQUE(puzzle_id, clue_id)
);
```

### אינדקסים
```sql
CREATE INDEX idx_cells_puzzle ON cells(puzzle_id);
CREATE INDEX idx_cells_position ON cells(puzzle_id, row, col);
CREATE INDEX idx_clues_puzzle ON clues(puzzle_id);
CREATE INDEX idx_clues_cell ON clues(cell_id);
```

---

## 5. ארכיטקטורת הקוד

### מבנה קבצים חדש
```
crossword_solver/
├── data/
│   └── crosswords.db
├── database/
│   ├── __init__.py
│   ├── db_manager.py        -- ניהול החיבור
│   ├── puzzle_repository.py -- CRUD לתשבצים
│   └── migrations.py        -- מיגרציות עתידיות
├── app.py
└── ...
```

### Class: DatabaseManager
```python
class DatabaseManager:
    """מנהל את החיבור ל-SQLite"""

    def __init__(self, db_path: str = "data/crosswords.db"):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """יוצר את הטבלאות אם לא קיימות"""

    def get_connection(self) -> sqlite3.Connection:
        """מחזיר connection"""

    def close(self):
        """סוגר את החיבור"""
```

### Class: PuzzleRepository
```python
class PuzzleRepository:
    """CRUD operations לתשבצים"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # שמירה
    def save_puzzle(self, name: str, grid: GridMatrix, image: np.ndarray) -> int:
        """שומר תשבץ חדש, מחזיר ID"""

    def update_puzzle(self, puzzle_id: int, grid: GridMatrix):
        """מעדכן תשבץ קיים"""

    # טעינה
    def load_puzzle(self, name: str) -> Tuple[GridMatrix, np.ndarray]:
        """טוען תשבץ לפי שם"""

    def load_puzzle_by_id(self, puzzle_id: int) -> Tuple[GridMatrix, np.ndarray]:
        """טוען תשבץ לפי ID"""

    # רשימה
    def list_puzzles(self) -> List[Dict]:
        """מחזיר רשימת כל התשבצים עם metadata"""
        # [{id, name, created_at, rows, cols}, ...]

    # מחיקה
    def delete_puzzle(self, puzzle_id: int):
        """מוחק תשבץ"""

    # בדיקה
    def puzzle_exists(self, name: str) -> bool:
        """בודק אם תשבץ בשם זה קיים"""
```

### Helper Functions
```python
def compress_image(image: np.ndarray) -> bytes:
    """דוחס תמונה ל-JPEG bytes"""
    _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buffer.tobytes()

def decompress_image(data: bytes) -> np.ndarray:
    """מפענח JPEG bytes לתמונה"""
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

def grid_to_db_format(grid: GridMatrix) -> Tuple[List[dict], List[dict]]:
    """ממיר GridMatrix לפורמט DB (cells, clues)"""

def db_to_grid_format(cells: List[dict], clues: List[dict], rows: int, cols: int) -> GridMatrix:
    """ממיר מ-DB בחזרה ל-GridMatrix"""
```

---

## 6. שינויים ב-UI (app.py)

### מסך הבית - כפתורים חדשים
```
+----------------------------------+
|  [העלה תמונה]  [טען תשבץ שמור]   |
+----------------------------------+
```

### לאחר זיהוי מוצלח - כפתור שמירה
```
+----------------------------------+
|  תוצאות (15 הגדרות)              |
|  [שמור תשבץ]                     |
+----------------------------------+
```

### דיאלוג שמירה
```
+----------------------------------+
|  שמור תשבץ                       |
|  שם: [________________]          |
|  [שמור] [ביטול]                  |
+----------------------------------+
```

### דיאלוג טעינה
```
+----------------------------------+
|  בחר תשבץ לטעינה                 |
|  +----------------------------+  |
|  | שם        | תאריך  | גודל |  |
|  | תשבץ 1    | 01/01  | 10x10|  |
|  | תשבץ 2    | 02/01  | 12x12|  |
|  +----------------------------+  |
|  [טען] [מחק] [ביטול]            |
+----------------------------------+
```

---

## 7. זרימת העבודה החדשה

### Flow א': סריקה חדשה
```
1. משתמש מעלה תמונה
2. לוחץ "סרוק"
3. Gemini מזהה
4. תוצאות מוצגות
5. משתמש לוחץ "שמור תשבץ"
6. דיאלוג שם → משתמש מקליד "תשבץ יום שישי"
7. נשמר ל-DB
8. הודעת הצלחה
```

### Flow ב': עבודה על תשבץ קיים
```
1. משתמש לוחץ "טען תשבץ שמור"
2. רשימת תשבצים מוצגת
3. משתמש בוחר תשבץ
4. GridMatrix + תמונה נטענים ל-session_state
5. תוצאות מוצגות מיידית (בלי לסרוק!)
6. משתמש יכול להמשיך לפתרון
```

---

## 8. שיקולי מיגרציה

### schema_version
כל תשבץ שומר `schema_version`. אם המבנה ישתנה:

```python
CURRENT_SCHEMA_VERSION = 1

def migrate_if_needed(puzzle_data: dict) -> dict:
    version = puzzle_data.get('schema_version', 1)

    if version < 2:
        # מיגרציה מ-1 ל-2
        puzzle_data = migrate_v1_to_v2(puzzle_data)

    if version < 3:
        # מיגרציה מ-2 ל-3
        puzzle_data = migrate_v2_to_v3(puzzle_data)

    return puzzle_data
```

---

## 9. סיכום

### מה נבנה:
1. **DatabaseManager** - ניהול SQLite
2. **PuzzleRepository** - CRUD לתשבצים
3. **UI changes** - כפתורי שמור/טען

### לא נבנה (מחוץ ל-scope):
- ייצוא/ייבוא JSON
- שיתוף תשבצים
- סטטיסטיקות
- חיפוש טקסט בהגדרות

### תלויות חדשות:
- אין! sqlite3 מובנה ב-Python

### הערכת זמן:
- DatabaseManager + PuzzleRepository: בינוני
- UI שמירה/טעינה: בינוני
- בדיקות: קצר

---

## 10. שאלות פתוחות לאישור

1. **מיקום DB** - `data/crosswords.db` מתאים?
2. **שמות כפולים** - מה לעשות אם משתמש מנסה לשמור בשם קיים?
   - להציג שגיאה?
   - לשאול אם לדרוס?
3. **מחיקה** - לאפשר מחיקת תשבצים מה-UI?
4. **תמונות דיבוג** - לשמור? (מגדיל את הקובץ)

---

*מסמך זה נכתב ב-2026-01-01 וממתין לאישור לפני יישום.*
