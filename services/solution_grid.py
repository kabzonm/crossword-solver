"""
Solution Grid Service
מטריצת הפתרון - מחזיקה את התשובות שהושבצו
"""

from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from models.clue_entry import ClueEntry, WritingDirection


class PlacementStatus(Enum):
    """סטטוס שיבוץ"""
    SUCCESS = "success"
    CONFLICT = "conflict"
    OUT_OF_BOUNDS = "out_of_bounds"
    INVALID_LENGTH = "invalid_length"


@dataclass
class SolutionCell:
    """משבצת בודדת במטריצת הפתרון"""
    letter: str = ""  # האות שהוכנסה
    confidence: float = 0.0  # ביטחון
    source_clues: List[str] = field(default_factory=list)  # הגדרות שתרמו לאות זו
    is_conflict: bool = False  # האם יש סתירה
    conflicting_letters: List[str] = field(default_factory=list)  # אותיות סותרות


@dataclass
class PlacementResult:
    """תוצאת ניסיון שיבוץ"""
    status: PlacementStatus
    conflicts: List[Tuple[int, int, str, str]] = field(default_factory=list)  # [(row, col, existing, new), ...]
    message: str = ""


class SolutionGrid:
    """
    מטריצת הפתרון.

    תפקידים:
    1. אחסון האותיות שהושבצו
    2. בדיקת התאמה לפני שיבוץ
    3. זיהוי סתירות
    4. מעקב אחרי מקור כל אות
    """

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.grid: List[List[SolutionCell]] = [
            [SolutionCell() for _ in range(cols)]
            for _ in range(rows)
        ]
        self._placed_clues: Set[str] = set()  # הגדרות שכבר שובצו

    def get_cell(self, row: int, col: int) -> Optional[SolutionCell]:
        """קבלת תוכן משבצת"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.grid[row][col]
        return None

    def get_letter(self, row: int, col: int) -> str:
        """קבלת האות במשבצת"""
        cell = self.get_cell(row, col)
        return cell.letter if cell else ""

    def can_place(self, clue: ClueEntry, answer: str) -> PlacementResult:
        """
        בודק האם אפשר לשבץ תשובה.

        Args:
            clue: ההגדרה
            answer: התשובה המוצעת

        Returns:
            PlacementResult עם סטטוס והסבר
        """
        # בדיקת אורך
        if len(answer) != len(clue.answer_cells):
            return PlacementResult(
                status=PlacementStatus.INVALID_LENGTH,
                message=f"Answer length {len(answer)} doesn't match expected {len(clue.answer_cells)}"
            )

        conflicts = []

        for i, (row, col) in enumerate(clue.answer_cells):
            # בדיקת גבולות
            if not (0 <= row < self.rows and 0 <= col < self.cols):
                return PlacementResult(
                    status=PlacementStatus.OUT_OF_BOUNDS,
                    message=f"Cell ({row}, {col}) is out of bounds"
                )

            # בדיקת סתירה
            existing = self.grid[row][col].letter
            new_letter = answer[i]

            if existing and existing != new_letter:
                conflicts.append((row, col, existing, new_letter))

        if conflicts:
            return PlacementResult(
                status=PlacementStatus.CONFLICT,
                conflicts=conflicts,
                message=f"Found {len(conflicts)} conflicts"
            )

        return PlacementResult(
            status=PlacementStatus.SUCCESS,
            message="OK"
        )

    def place_answer(
        self,
        clue: ClueEntry,
        answer: str,
        confidence: float = 1.0,
        force: bool = False
    ) -> PlacementResult:
        """
        משבץ תשובה במטריצה.

        Args:
            clue: ההגדרה
            answer: התשובה
            confidence: רמת ביטחון
            force: האם לשבץ גם אם יש סתירות

        Returns:
            PlacementResult
        """
        # בדיקה
        result = self.can_place(clue, answer)

        if result.status == PlacementStatus.CONFLICT and not force:
            return result

        if result.status in [PlacementStatus.OUT_OF_BOUNDS, PlacementStatus.INVALID_LENGTH]:
            return result

        # שיבוץ
        for i, (row, col) in enumerate(clue.answer_cells):
            cell = self.grid[row][col]
            new_letter = answer[i]

            if cell.letter and cell.letter != new_letter:
                # יש סתירה
                cell.is_conflict = True
                if new_letter not in cell.conflicting_letters:
                    cell.conflicting_letters.append(new_letter)

                if force:
                    cell.letter = new_letter  # דורס
            else:
                cell.letter = new_letter

            cell.confidence = max(cell.confidence, confidence)

            if clue.id not in cell.source_clues:
                cell.source_clues.append(clue.id)

        self._placed_clues.add(clue.id)
        clue.chosen_answer = answer
        clue.is_solved = True

        return PlacementResult(
            status=PlacementStatus.SUCCESS,
            conflicts=result.conflicts,
            message=f"Placed '{answer}' for clue {clue.id}"
        )

    def remove_answer(self, clue: ClueEntry) -> bool:
        """
        מסיר תשובה שהושבצה (לצורך backtracking).
        """
        if clue.id not in self._placed_clues:
            return False

        for row, col in clue.answer_cells:
            cell = self.grid[row][col]

            # הסרת ה-clue מהמקורות
            if clue.id in cell.source_clues:
                cell.source_clues.remove(clue.id)

            # אם אין יותר מקורות - ניקוי המשבצת
            if not cell.source_clues:
                cell.letter = ""
                cell.confidence = 0.0
                cell.is_conflict = False
                cell.conflicting_letters = []

        self._placed_clues.remove(clue.id)
        clue.chosen_answer = None
        clue.is_solved = False

        return True

    def get_known_letters(self, cells: List[Tuple[int, int]]) -> Dict[int, str]:
        """
        מחזיר אותיות ידועות עבור רשימת משבצות.

        Args:
            cells: רשימת משבצות [(row, col), ...]

        Returns:
            מיפוי אינדקס → אות
        """
        known = {}
        for i, (row, col) in enumerate(cells):
            letter = self.get_letter(row, col)
            if letter:
                known[i] = letter
        return known

    def get_conflicts(self) -> List[Tuple[int, int]]:
        """מחזיר רשימת משבצות עם סתירות"""
        conflicts = []
        for row in range(self.rows):
            for col in range(self.cols):
                if self.grid[row][col].is_conflict:
                    conflicts.append((row, col))
        return conflicts

    def get_completion_percentage(self) -> float:
        """מחזיר אחוז מילוי"""
        filled = sum(
            1 for row in self.grid for cell in row if cell.letter
        )
        total = self.rows * self.cols
        return (filled / total * 100) if total > 0 else 0

    def get_statistics(self) -> Dict:
        """סטטיסטיקות"""
        filled = sum(1 for row in self.grid for cell in row if cell.letter)
        conflicts = len(self.get_conflicts())
        avg_confidence = sum(
            cell.confidence for row in self.grid for cell in row if cell.letter
        ) / filled if filled > 0 else 0

        return {
            'total_cells': self.rows * self.cols,
            'filled_cells': filled,
            'empty_cells': self.rows * self.cols - filled,
            'conflicts': conflicts,
            'completion_percentage': self.get_completion_percentage(),
            'avg_confidence': avg_confidence,
            'placed_clues': len(self._placed_clues)
        }

    def to_string_grid(self) -> str:
        """מחזיר ייצוג טקסטואלי של הגריד"""
        lines = []
        for row in self.grid:
            line = " ".join(
                cell.letter if cell.letter else "." for cell in row
            )
            lines.append(line)
        return "\n".join(lines)

    def to_matrix(self) -> List[List[str]]:
        """מחזיר מטריצה של אותיות"""
        return [
            [cell.letter for cell in row]
            for row in self.grid
        ]

    def get_answer_for_clue(self, clue: ClueEntry) -> str:
        """מחזיר את התשובה הנוכחית להגדרה (מהאותיות שכבר שובצו)"""
        letters = []
        for row, col in clue.answer_cells:
            letter = self.get_letter(row, col)
            letters.append(letter if letter else "_")
        return "".join(letters)

    def clear(self) -> None:
        """ניקוי המטריצה"""
        for row in range(self.rows):
            for col in range(self.cols):
                self.grid[row][col] = SolutionCell()
        self._placed_clues.clear()
