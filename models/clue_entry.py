"""
ClueEntry Model
מודל להגדרה בודדת בתשבץ
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum


class WritingDirection(Enum):
    """כיוון כתיבת התשובה"""
    DOWN = "down"
    UP = "up"
    RIGHT = "right"
    LEFT = "left"


@dataclass
class ClueEntry:
    """
    מייצג הגדרה בודדת בתשבץ.
    זה המודל המרכזי לניהול כל המידע על הגדרה.
    """

    # === זיהוי ===
    id: str  # מזהה ייחודי: "clue_0_0_full" או "clue_0_0_top"
    source_cell: Tuple[int, int]  # (row, col) של משבצת המקור
    zone: str = "full"  # "full" / "top" / "bottom" / "left" / "right"

    # === תוכן ===
    text: str = ""  # טקסט ההגדרה ("בעל חיים")
    ocr_confidence: float = 0.0  # ביטחון ב-OCR

    # === חץ ===
    arrow_direction: str = "none"  # "down" / "right" / "down-right" וכו'
    arrow_position: str = "unknown"  # "top-right" / "bottom-left" - מיקום החץ בתמונה
    arrow_confidence: float = 0.0

    # === מיקום התשובה (מחושב מהחץ) ===
    answer_start_cell: Optional[Tuple[int, int]] = None  # היכן מתחילה התשובה
    writing_direction: Optional[WritingDirection] = None  # כיוון הכתיבה
    answer_length: int = 0  # כמה אותיות
    answer_cells: List[Tuple[int, int]] = field(default_factory=list)  # כל המשבצות

    # === פתרון ===
    known_letters: Dict[int, str] = field(default_factory=dict)  # אותיות ידועות {0: 'כ', 2: 'ב'}
    candidates: List[Tuple[str, float]] = field(default_factory=list)  # [(תשובה, ביטחון), ...]
    chosen_answer: Optional[str] = None  # התשובה שנבחרה

    # === מטא ===
    overall_confidence: float = 0.0
    is_solved: bool = False
    error: Optional[str] = None

    def __post_init__(self):
        """חישוב ביטחון כולל"""
        if self.ocr_confidence > 0 or self.arrow_confidence > 0:
            self.overall_confidence = (self.ocr_confidence + self.arrow_confidence) / 2

    def get_constraint_string(self) -> str:
        """
        מחזיר מחרוזת המייצגת את האילוצים הידועים.
        לדוגמה: "כ_ב_" עבור מילה באורך 4 עם אותיות ידועות במיקומים 0 ו-2
        """
        if self.answer_length == 0:
            return ""

        result = ["_"] * self.answer_length
        for pos, letter in self.known_letters.items():
            if 0 <= pos < self.answer_length:
                result[pos] = letter
        return "".join(result)

    def matches_answer(self, answer: str) -> bool:
        """
        בודק האם תשובה מתאימה לאילוצים הידועים.
        """
        if len(answer) != self.answer_length:
            return False

        for pos, letter in self.known_letters.items():
            if pos < len(answer) and answer[pos] != letter:
                return False

        return True

    def to_dict(self) -> dict:
        """המרה ל-dictionary לשמירה/הצגה"""
        return {
            'id': self.id,
            'source_cell': self.source_cell,
            'zone': self.zone,
            'text': self.text,
            'arrow_direction': self.arrow_direction,
            'arrow_position': self.arrow_position,
            'answer_start': self.answer_start_cell,
            'writing_direction': self.writing_direction.value if self.writing_direction else None,
            'answer_length': self.answer_length,
            'answer_cells': self.answer_cells,
            'known_letters': self.known_letters,
            'constraint': self.get_constraint_string(),
            'candidates': self.candidates[:5],  # רק 5 ראשונים
            'chosen_answer': self.chosen_answer,
            'confidence': {
                'ocr': self.ocr_confidence,
                'arrow': self.arrow_confidence,
                'overall': self.overall_confidence
            },
            'is_solved': self.is_solved
        }

    @classmethod
    def from_parsed_clue(
        cls,
        row: int,
        col: int,
        parsed_clue: dict,
        zone: str = "full"
    ) -> 'ClueEntry':
        """
        יוצר ClueEntry מ-parsed_clue שמגיע מה-BatchProcessor
        """
        clue_id = f"clue_{row}_{col}_{zone}"

        return cls(
            id=clue_id,
            source_cell=(row, col),
            zone=zone,
            text=parsed_clue.get('text', ''),
            ocr_confidence=parsed_clue.get('ocr_confidence', 0.0),
            arrow_direction=parsed_clue.get('path', 'none'),
            arrow_position=parsed_clue.get('arrow_position', 'unknown'),
            arrow_confidence=parsed_clue.get('arrow_confidence', 0.0),
            overall_confidence=parsed_clue.get('confidence', 0.0)
        )
