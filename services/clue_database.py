"""
Clue Database Service
ניהול מאגר ההגדרות
"""

from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
import json

from models.clue_entry import ClueEntry, WritingDirection
from models.grid import GridMatrix, CellType
from services.arrow_offset_calculator import ArrowOffsetCalculator


class ClueDatabase:
    """
    מנהל את מאגר ההגדרות של התשבץ.

    תפקידים:
    1. אחסון כל ההגדרות
    2. חישוב מיקום תחילת תשובה ואורכה
    3. זיהוי הצלבות בין הגדרות
    4. עדכון אותיות ידועות
    """

    def __init__(self):
        self.clues: List[ClueEntry] = []
        self._clue_map: Dict[str, ClueEntry] = {}  # מיפוי לפי ID
        self._cell_to_clues: Dict[Tuple[int, int], List[str]] = {}  # מיפוי משבצת להגדרות

    def add_clue(self, clue: ClueEntry) -> None:
        """הוספת הגדרה למאגר"""
        self.clues.append(clue)
        self._clue_map[clue.id] = clue

        # עדכון מיפוי משבצות
        for cell in clue.answer_cells:
            if cell not in self._cell_to_clues:
                self._cell_to_clues[cell] = []
            self._cell_to_clues[cell].append(clue.id)

    def get_clue(self, clue_id: str) -> Optional[ClueEntry]:
        """קבלת הגדרה לפי ID"""
        return self._clue_map.get(clue_id)

    def get_clues_for_cell(self, row: int, col: int) -> List[ClueEntry]:
        """קבלת כל ההגדרות שעוברות דרך משבצת"""
        clue_ids = self._cell_to_clues.get((row, col), [])
        return [self._clue_map[cid] for cid in clue_ids if cid in self._clue_map]

    def build_from_grid(self, grid: GridMatrix) -> None:
        """
        בונה את מאגר ההגדרות מה-GridMatrix.
        קורא אחרי שה-BatchProcessor סיים לעבד את כל המשבצות.
        """
        self.clues = []
        self._clue_map = {}
        self._cell_to_clues = {}

        for row in range(grid.rows):
            for col in range(grid.cols):
                cell = grid.matrix[row][col]

                if cell.type != CellType.CLUE:
                    continue

                # קריאת parsed_clues מהתא
                parsed_clues = getattr(cell, 'parsed_clues', [])

                for i, parsed in enumerate(parsed_clues):
                    # קביעת zone
                    zone = parsed.get('zone', 'full')
                    if zone == 'full_cell':
                        zone = 'full'

                    # יצירת ClueEntry
                    clue = ClueEntry.from_parsed_clue(row, col, parsed, zone)

                    # חישוב מיקום תחילת התשובה
                    self._calculate_answer_location(clue, grid)

                    self.add_clue(clue)

        # זיהוי הצלבות ועדכון known_letters
        self._find_intersections()

    def _calculate_answer_location(self, clue: ClueEntry, grid: GridMatrix) -> None:
        """מחשב היכן מתחילה התשובה ואת אורכה"""
        if clue.arrow_direction in ['none', 'unknown', '']:
            return

        # חישוב נקודת התחלה
        start_row, start_col, writing_dir = ArrowOffsetCalculator.calculate_answer_start(
            clue.source_cell[0],
            clue.source_cell[1],
            clue.arrow_direction
        )

        # בדיקה שנקודת ההתחלה בתוך הגריד
        if not (0 <= start_row < grid.rows and 0 <= start_col < grid.cols):
            return

        # בדיקה שנקודת ההתחלה היא משבצת SOLUTION
        if grid.matrix[start_row][start_col].type != CellType.SOLUTION:
            return

        clue.answer_start_cell = (start_row, start_col)
        clue.writing_direction = writing_dir

        # ספירת משבצות SOLUTION ברצף
        answer_cells = self._trace_answer_cells(grid, start_row, start_col, writing_dir)
        clue.answer_cells = answer_cells
        clue.answer_length = len(answer_cells)

    def _trace_answer_cells(
        self,
        grid: GridMatrix,
        start_row: int,
        start_col: int,
        direction: WritingDirection
    ) -> List[Tuple[int, int]]:
        """עוקב אחרי משבצות SOLUTION ברצף מנקודת ההתחלה"""
        cells = []
        row, col = start_row, start_col

        # כיוון התקדמות
        d_row, d_col = {
            WritingDirection.DOWN: (1, 0),
            WritingDirection.UP: (-1, 0),
            WritingDirection.RIGHT: (0, 1),
            WritingDirection.LEFT: (0, -1),
        }.get(direction, (0, 0))

        # מעקב עד שיוצאים מהגריד או פוגעים במשבצת שאינה SOLUTION
        while 0 <= row < grid.rows and 0 <= col < grid.cols:
            cell = grid.matrix[row][col]

            if cell.type != CellType.SOLUTION:
                break

            cells.append((row, col))
            row += d_row
            col += d_col

        return cells

    def _find_intersections(self) -> None:
        """מזהה הצלבות בין הגדרות"""
        # לכל משבצת, אם יש יותר מהגדרה אחת שעוברת בה - יש הצלבה
        for cell, clue_ids in self._cell_to_clues.items():
            if len(clue_ids) > 1:
                # יש הצלבה - כל ההגדרות חולקות את האות הזו
                pass  # נטפל בזה כשנשבץ תשובות

    def get_intersections(self, clue: ClueEntry) -> Dict[int, List[Tuple[str, int]]]:
        """
        מחזיר את ההצלבות של הגדרה מסוימת.

        Returns:
            מיפוי: אינדקס באות → [(clue_id, אינדקס באות של ההגדרה האחרת), ...]
        """
        intersections = {}

        for i, cell in enumerate(clue.answer_cells):
            other_clues = self.get_clues_for_cell(cell[0], cell[1])

            for other in other_clues:
                if other.id == clue.id:
                    continue

                # מציאת האינדקס של המשבצת בהגדרה האחרת
                try:
                    other_idx = other.answer_cells.index(cell)
                    if i not in intersections:
                        intersections[i] = []
                    intersections[i].append((other.id, other_idx))
                except ValueError:
                    pass

        return intersections

    def update_known_letters(self, clue: ClueEntry, answer: str) -> None:
        """
        מעדכן אותיות ידועות בהגדרות אחרות אחרי שיבוץ תשובה.
        """
        if len(answer) != len(clue.answer_cells):
            return

        for i, cell in enumerate(clue.answer_cells):
            letter = answer[i]

            # עדכון כל ההגדרות שעוברות במשבצת הזו
            for other in self.get_clues_for_cell(cell[0], cell[1]):
                if other.id == clue.id:
                    continue

                # מציאת האינדקס בהגדרה האחרת
                try:
                    other_idx = other.answer_cells.index(cell)
                    other.known_letters[other_idx] = letter
                except ValueError:
                    pass

    def get_unsolved_clues(self) -> List[ClueEntry]:
        """מחזיר הגדרות שעדיין לא נפתרו"""
        return [c for c in self.clues if not c.is_solved]

    def get_clues_sorted_by_difficulty(self) -> List[ClueEntry]:
        """
        מחזיר הגדרות ממוינות לפי קושי (קל לקשה).

        קריטריונים:
        1. כמה אותיות ידועות (יותר = קל יותר)
        2. אורך התשובה (קצר = קל יותר)
        3. ביטחון OCR (גבוה = קל יותר)
        """
        def difficulty_score(clue: ClueEntry) -> float:
            if clue.answer_length == 0:
                return float('inf')  # אם אין אורך - בסוף

            known_ratio = len(clue.known_letters) / clue.answer_length
            length_penalty = clue.answer_length / 10  # מילים ארוכות יותר קשות
            confidence_bonus = clue.overall_confidence

            # ציון נמוך = קל יותר
            return -known_ratio + length_penalty - confidence_bonus

        return sorted(self.get_unsolved_clues(), key=difficulty_score)

    def get_statistics(self) -> Dict:
        """מחזיר סטטיסטיקות על המאגר"""
        total = len(self.clues)
        solved = sum(1 for c in self.clues if c.is_solved)
        with_length = sum(1 for c in self.clues if c.answer_length > 0)
        with_known = sum(1 for c in self.clues if len(c.known_letters) > 0)

        return {
            'total_clues': total,
            'solved': solved,
            'unsolved': total - solved,
            'with_answer_length': with_length,
            'with_known_letters': with_known,
            'avg_answer_length': sum(c.answer_length for c in self.clues) / total if total > 0 else 0,
            'avg_confidence': sum(c.overall_confidence for c in self.clues) / total if total > 0 else 0,
        }

    def to_dict(self) -> Dict:
        """המרה ל-dictionary לשמירה"""
        return {
            'clues': [c.to_dict() for c in self.clues],
            'statistics': self.get_statistics()
        }

    def to_json(self) -> str:
        """המרה ל-JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def clear(self) -> None:
        """ניקוי המאגר"""
        self.clues = []
        self._clue_map = {}
        self._cell_to_clues = {}
