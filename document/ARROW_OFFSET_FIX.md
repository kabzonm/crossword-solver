# תיקון חישוב אופסט חצים - Arrow Offset Fix

## תאריך: 2025-12-29

---

## הבעיה שזוהתה

חישוב האופסט לחצים L-shaped היה **שגוי**.

### דוגמה לבעיה:

משבצת הגדרה במיקום **(1,1)** עם חץ **"down-right"** (למטה-ימינה):

```
         col 0   col 1   col 2   col 3
row 0    [  ]    [  ]    [  ]    [  ]
row 1    [  ]   [הגדרה]  [  ]    [  ]
                  ↓→
row 2    [  ]   [תחילה]→ [  ] → [  ]
```

**מה הקוד הישן עשה:**
```python
'down-right': ArrowOffset(1, 1, WritingDirection.RIGHT)
# תוצאה: התשובה מתחילה ב-(2,2) - שגוי!
```

**מה צריך להיות:**
- החץ אומר: "לך למטה, ואז פנה ימינה"
- התשובה מתחילה במשבצת **(2,1)** - שורה אחת למטה, **אותה עמודה**
- כיוון הכתיבה: ימינה → (2,1), (2,2), (2,3)...

---

## הכלל הנכון

> **האופסט נקבע לפי הכיוון הראשון של החץ.**
> **כיוון הכתיבה נקבע לפי הכיוון השני של החץ.**

### פירוט:

| חץ | פירוש | כיוון ראשון | כיוון שני | אופסט (row, col) | כיוון כתיבה |
|----|-------|-------------|-----------|------------------|-------------|
| `down` | למטה | down | - | **(+1, 0)** | DOWN |
| `up` | למעלה | up | - | **(-1, 0)** | UP |
| `right` | ימינה | right | - | **(0, +1)** | RIGHT |
| `left` | שמאלה | left | - | **(0, -1)** | LEFT |
| `down-right` | למטה ואז ימינה | down | right | **(+1, 0)** | RIGHT |
| `down-left` | למטה ואז שמאלה | down | left | **(+1, 0)** | LEFT |
| `up-right` | למעלה ואז ימינה | up | right | **(-1, 0)** | RIGHT |
| `up-left` | למעלה ואז שמאלה | up | left | **(-1, 0)** | LEFT |
| `right-down` | ימינה ואז למטה | right | down | **(0, +1)** | DOWN |
| `right-up` | ימינה ואז למעלה | right | up | **(0, +1)** | UP |
| `left-down` | שמאלה ואז למטה | left | down | **(0, -1)** | DOWN |
| `left-up` | שמאלה ואז למעלה | left | up | **(0, -1)** | UP |

---

## איור ויזואלי

### חץ פשוט: `down`
```
[הגדרה]
   ↓
[תחילה]  ← התשובה מתחילה כאן
   ↓
[  ]
   ↓
[  ]
```
- אופסט: (+1, 0)
- כתיבה: למטה

### חץ L-shaped: `down-right`
```
[הגדרה]
   ↓
[תחילה] → [  ] → [  ]
   ↑
   └── התשובה מתחילה כאן ונכתבת ימינה
```
- אופסט: (+1, 0) - שורה אחת למטה
- כתיבה: ימינה

### חץ L-shaped: `right-down`
```
[הגדרה] → [תחילה]  ← התשובה מתחילה כאן
              ↓
            [  ]
              ↓
            [  ]
```
- אופסט: (0, +1) - עמודה אחת ימינה
- כתיבה: למטה

---

## הקוד המתוקן

### קובץ: `services/arrow_offset_calculator.py`

```python
# מיפוי מלא של כל סוגי החצים - מתוקן!
ARROW_OFFSETS = {
    # === חצים פשוטים ===
    'down': ArrowOffset(1, 0, WritingDirection.DOWN),
    'up': ArrowOffset(-1, 0, WritingDirection.UP),
    'right': ArrowOffset(0, 1, WritingDirection.RIGHT),
    'left': ArrowOffset(0, -1, WritingDirection.LEFT),

    # === חצים L-shaped: מתחיל למטה ===
    # האופסט הוא לפי הכיוון הראשון (down = +1,0)
    # כיוון הכתיבה הוא לפי הכיוון השני
    'down-right': ArrowOffset(1, 0, WritingDirection.RIGHT),  # תוקן!
    'down-left': ArrowOffset(1, 0, WritingDirection.LEFT),    # תוקן!

    # === חצים L-shaped: מתחיל למעלה ===
    'up-right': ArrowOffset(-1, 0, WritingDirection.RIGHT),   # תוקן!
    'up-left': ArrowOffset(-1, 0, WritingDirection.LEFT),     # תוקן!

    # === חצים L-shaped: מתחיל ימינה ===
    'right-down': ArrowOffset(0, 1, WritingDirection.DOWN),   # תוקן!
    'right-up': ArrowOffset(0, 1, WritingDirection.UP),       # תוקן!

    # === חצים L-shaped: מתחיל שמאלה ===
    'left-down': ArrowOffset(0, -1, WritingDirection.DOWN),   # תוקן!
    'left-up': ArrowOffset(0, -1, WritingDirection.UP),       # תוקן!

    # === תאימות לאחור - פורמט ישן ===
    'straight-down': ArrowOffset(1, 0, WritingDirection.DOWN),
    'straight-up': ArrowOffset(-1, 0, WritingDirection.UP),
    'straight-right': ArrowOffset(0, 1, WritingDirection.RIGHT),
    'straight-left': ArrowOffset(0, -1, WritingDirection.LEFT),

    'start-down-turn-right': ArrowOffset(1, 0, WritingDirection.RIGHT),  # תוקן!
    'start-down-turn-left': ArrowOffset(1, 0, WritingDirection.LEFT),    # תוקן!
    'start-up-turn-right': ArrowOffset(-1, 0, WritingDirection.RIGHT),   # תוקן!
    'start-up-turn-left': ArrowOffset(-1, 0, WritingDirection.LEFT),     # תוקן!
    'start-right-turn-down': ArrowOffset(0, 1, WritingDirection.DOWN),   # תוקן!
    'start-right-turn-up': ArrowOffset(0, 1, WritingDirection.UP),       # תוקן!
    'start-left-turn-down': ArrowOffset(0, -1, WritingDirection.DOWN),   # תוקן!
    'start-left-turn-up': ArrowOffset(0, -1, WritingDirection.UP),       # תוקן!

    # ברירת מחדל
    'none': ArrowOffset(0, 0, WritingDirection.DOWN),
    'unknown': ArrowOffset(0, 0, WritingDirection.DOWN),
}
```

---

## השוואה: לפני ואחרי

| חץ | אופסט ישן (שגוי) | אופסט חדש (נכון) |
|----|------------------|------------------|
| `down-right` | (+1, +1) | **(+1, 0)** |
| `down-left` | (+1, -1) | **(+1, 0)** |
| `up-right` | (-1, +1) | **(-1, 0)** |
| `up-left` | (-1, -1) | **(-1, 0)** |
| `right-down` | (+1, +1) | **(0, +1)** |
| `right-up` | (-1, +1) | **(0, +1)** |
| `left-down` | (+1, -1) | **(0, -1)** |
| `left-up` | (-1, -1) | **(0, -1)** |

---

## קבצים לעדכון

| קובץ | שינוי נדרש |
|------|-----------|
| `services/arrow_offset_calculator.py` | תיקון טבלת ARROW_OFFSETS |
| `docs/ARCHITECTURE.md` | עדכון טבלת האופסטים |

---

## בדיקות לאחר התיקון

### בדיקה 1: חץ down-right
```python
from services.arrow_offset_calculator import ArrowOffsetCalculator

result = ArrowOffsetCalculator.calculate_answer_start(1, 1, 'down-right')
assert result == (2, 1, WritingDirection.RIGHT), f"Expected (2,1,RIGHT), got {result}"
```

### בדיקה 2: חץ right-down
```python
result = ArrowOffsetCalculator.calculate_answer_start(1, 1, 'right-down')
assert result == (1, 2, WritingDirection.DOWN), f"Expected (1,2,DOWN), got {result}"
```

### בדיקה 3: חץ פשוט down
```python
result = ArrowOffsetCalculator.calculate_answer_start(1, 1, 'down')
assert result == (2, 1, WritingDirection.DOWN), f"Expected (2,1,DOWN), got {result}"
```

---

## סיכום

הבעיה הייתה בהבנה השגויה של חצים L-shaped:
- **שגוי:** חשבנו שהחץ מציין אופסט אלכסוני (למשל +1,+1)
- **נכון:** החץ מציין לאן ללכת (כיוון ראשון) ואז לאן לפנות לכתיבה (כיוון שני)

התיקון פשוט - שינוי ערכי האופסט בטבלה כך שהאופסט יהיה רק לפי הכיוון הראשון של החץ.
