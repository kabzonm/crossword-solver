"""
Arrow Offset Calculator
חישוב מיקום תחילת התשובה בהתבסס על סוג החץ
"""

from typing import Tuple, Optional
from dataclasses import dataclass
from models.clue_entry import WritingDirection


@dataclass
class ArrowOffset:
    """תוצאת חישוב אופסט"""
    row_offset: int  # כמה שורות לזוז
    col_offset: int  # כמה עמודות לזוז
    writing_direction: WritingDirection  # כיוון הכתיבה


class ArrowOffsetCalculator:
    """
    מחשב את האופסט (היכן מתחילה התשובה) בהתבסס על סוג החץ.

    הכלל: האופסט נקבע לפי הכיוון הראשון של החץ,
          כיוון הכתיבה נקבע לפי הכיוון השני.

    חצים פשוטים - התשובה מתחילה במשבצת הסמוכה:
        down  → שורה אחת למטה (+1, 0), כתיבה למטה
        right → עמודה אחת ימינה (0, +1), כתיבה ימינה

    חצים L-shaped - האופסט לפי הכיוון הראשון בלבד:
        down-right → למטה ואז ימינה = התחלה ב(+1, 0), כתיבה ימינה
        right-down → ימינה ואז למטה = התחלה ב(0, +1), כתיבה למטה

    דוגמה:
        משבצת הגדרה (1,1) עם חץ down-right:
        - האופסט: (+1, 0) = התשובה מתחילה ב-(2, 1)
        - כיוון כתיבה: RIGHT = (2,1), (2,2), (2,3)...
    """

    # מיפוי מלא של כל סוגי החצים - מתוקן!
    # הכלל: האופסט לפי הכיוון הראשון, כיוון הכתיבה לפי הכיוון השני
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

    @classmethod
    def get_offset(cls, arrow_direction: str) -> ArrowOffset:
        """
        מחזיר את האופסט עבור סוג חץ.

        Args:
            arrow_direction: סוג החץ (למשל "down", "down-right")

        Returns:
            ArrowOffset עם row_offset, col_offset, writing_direction
        """
        # נרמול - המרה ל-lowercase והסרת רווחים
        normalized = arrow_direction.lower().strip().replace(' ', '-')

        return cls.ARROW_OFFSETS.get(
            normalized,
            ArrowOffset(0, 0, WritingDirection.DOWN)  # ברירת מחדל
        )

    @classmethod
    def calculate_answer_start(
        cls,
        clue_row: int,
        clue_col: int,
        arrow_direction: str
    ) -> Tuple[int, int, WritingDirection]:
        """
        מחשב היכן מתחילה התשובה.

        Args:
            clue_row: שורת משבצת ההגדרה
            clue_col: עמודת משבצת ההגדרה
            arrow_direction: סוג החץ

        Returns:
            (start_row, start_col, writing_direction)
        """
        offset = cls.get_offset(arrow_direction)

        start_row = clue_row + offset.row_offset
        start_col = clue_col + offset.col_offset

        return (start_row, start_col, offset.writing_direction)

    @classmethod
    def get_writing_direction(cls, arrow_direction: str) -> WritingDirection:
        """מחזיר רק את כיוון הכתיבה"""
        offset = cls.get_offset(arrow_direction)
        return offset.writing_direction

    @classmethod
    def is_valid_arrow(cls, arrow_direction: str) -> bool:
        """בודק אם זה סוג חץ מוכר"""
        normalized = arrow_direction.lower().strip().replace(' ', '-')
        return normalized in cls.ARROW_OFFSETS

    @classmethod
    def normalize_direction(cls, arrow_direction: str) -> str:
        """
        מנרמל את שם החץ לפורמט סטנדרטי.
        למשל: "start-down-turn-right" -> "down-right"
        """
        normalized = arrow_direction.lower().strip().replace(' ', '-')

        # המרה מפורמט ישן לחדש
        conversions = {
            'straight-down': 'down',
            'straight-up': 'up',
            'straight-right': 'right',
            'straight-left': 'left',
            'start-down-turn-right': 'down-right',
            'start-down-turn-left': 'down-left',
            'start-up-turn-right': 'up-right',
            'start-up-turn-left': 'up-left',
            'start-right-turn-down': 'right-down',
            'start-right-turn-up': 'right-up',
            'start-left-turn-down': 'left-down',
            'start-left-turn-up': 'left-up',
        }

        return conversions.get(normalized, normalized)

    @classmethod
    def get_arrow_icon(cls, arrow_direction: str) -> str:
        """מחזיר אייקון לחץ"""
        icons = {
            'down': '↓',
            'up': '↑',
            'right': '→',
            'left': '←',
            'down-right': '↓→',
            'down-left': '↓←',
            'up-right': '↑→',
            'up-left': '↑←',
            'right-down': '→↓',
            'right-up': '→↑',
            'left-down': '←↓',
            'left-up': '←↑',
            'none': '○',
            'unknown': '?',
        }

        normalized = cls.normalize_direction(arrow_direction)
        return icons.get(normalized, '?')
