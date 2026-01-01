"""
Puzzle Solver Service
אלגוריתם פתרון התשבץ - Constraint Satisfaction עם Backtracking
תמיכה ב-callbacks לכל אות ותשובות ידניות
"""

import time
from typing import List, Dict, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from models.clue_entry import ClueEntry
from services.clue_database import ClueDatabase
from services.solution_grid import SolutionGrid, PlacementStatus
from services.clue_solver import ClueSolver, SolverResult


class SolveStatus(Enum):
    """סטטוס פתרון"""
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"      # נעצר ע"י המשתמש
    SOLVED = "solved"
    STUCK = "stuck"        # לא מצליח להתקדם
    FAILED = "failed"      # נכשל אחרי כל הניסיונות


@dataclass
class SolveStep:
    """צעד בתהליך הפתרון"""
    clue_id: str
    answer: str
    confidence: float
    action: str  # "place" / "backtrack" / "manual"
    success: bool
    message: str = ""
    is_manual: bool = False  # האם זו תשובה ידנית


@dataclass
class SolveProgress:
    """מעקב התקדמות"""
    total_clues: int
    solved_clues: int
    manual_clues: int = 0  # כמה הוכנסו ידנית
    current_clue: Optional[str] = None
    steps: List[SolveStep] = field(default_factory=list)
    backtracks: int = 0
    start_time: float = 0.0
    status: SolveStatus = SolveStatus.IN_PROGRESS


@dataclass
class SolverCallbacks:
    """Callbacks לעדכוני UI"""
    on_clue_start: Optional[Callable[[str, List[Tuple[int, int]]], None]] = None
    on_letter_placed: Optional[Callable[[int, int, str, int], None]] = None  # row, col, letter, index
    on_clue_solved: Optional[Callable[[str, str, float], None]] = None  # clue_id, answer, confidence
    on_backtrack: Optional[Callable[[str, List[Tuple[int, int, str]]], None]] = None  # clue_id, removed_letters
    on_progress: Optional[Callable[[SolveProgress], None]] = None
    on_completed: Optional[Callable[[Dict], None]] = None

    # השהיה בין אותיות (ms) - לאפקט ויזואלי
    letter_delay_ms: int = 150


class PuzzleSolver:
    """
    פותר את התשבץ באמצעות אלגוריתם Constraint Satisfaction עם Backtracking.

    תכונות:
    - Callbacks לכל אות (לא רק לכל מילה)
    - תמיכה בתשובות ידניות כאילוצים קבועים
    - עצירה והמשך
    - Backtrack שלא נוגע בתשובות ידניות
    """

    def __init__(
        self,
        clue_database: ClueDatabase,
        solution_grid: SolutionGrid,
        clue_solver: ClueSolver,
        max_backtracks: int = 100
    ):
        """
        Args:
            clue_database: מאגר ההגדרות
            solution_grid: מטריצת הפתרון
            clue_solver: שירות קבלת תשובות
            max_backtracks: מקסימום backtracking לפני וויתור
        """
        self.clue_db = clue_database
        self.solution = solution_grid
        self.solver = clue_solver
        self.max_backtracks = max_backtracks

        self.progress = SolveProgress(
            total_clues=len(clue_database.clues),
            solved_clues=0
        )

        # מעקב לצורך backtracking
        self._placement_stack: List[Tuple[ClueEntry, str, bool]] = []  # [(clue, answer, is_manual), ...]
        self._tried_answers: Dict[str, List[str]] = {}  # clue_id → [answers tried]

        # תשובות ידניות - אילוצים קבועים
        self.manual_answers: Dict[str, str] = {}  # clue_id -> answer
        self.locked_cells: Set[Tuple[int, int]] = set()  # משבצות נעולות

        # בקרת ריצה
        self._should_pause = False
        self._is_running = False

        # Callbacks
        self.callbacks = SolverCallbacks()

    def set_callbacks(self, callbacks: SolverCallbacks) -> None:
        """הגדרת callbacks"""
        self.callbacks = callbacks

    def set_manual_answer(self, clue: ClueEntry, answer: str) -> bool:
        """
        הגדרת תשובה ידנית - הופכת לאילוץ קבוע.

        Args:
            clue: ההגדרה
            answer: התשובה

        Returns:
            True אם הצליח
        """
        # וולידציה
        if len(answer) != clue.answer_length:
            return False

        # בדיקת התאמה לאותיות ידועות
        if not clue.matches_answer(answer):
            return False

        # בדיקת קונפליקטים עם תשובות ידניות אחרות
        for i, (row, col) in enumerate(clue.answer_cells):
            existing = self.solution.get_letter(row, col)
            if existing and existing != answer[i]:
                # יש קונפליקט עם תשובה קיימת
                # בדוק אם המשבצת נעולה
                if (row, col) in self.locked_cells:
                    return False

        # שמירת התשובה הידנית
        self.manual_answers[clue.id] = answer
        self.locked_cells.update(clue.answer_cells)

        # שיבוץ בגריד
        self.solution.place_answer(clue, answer, confidence=1.0)
        self._placement_stack.append((clue, answer, True))  # True = manual

        # עדכון אותיות ידועות להגדרות מצטלבות
        self.clue_db.update_known_letters(clue, answer)

        # עדכון התקדמות
        self.progress.solved_clues += 1
        self.progress.manual_clues += 1

        # תיעוד
        step = SolveStep(
            clue_id=clue.id,
            answer=answer,
            confidence=1.0,
            action="manual",
            success=True,
            message="Manual entry - locked",
            is_manual=True
        )
        self.progress.steps.append(step)

        return True

    def clear_manual_answer(self, clue: ClueEntry) -> bool:
        """
        מחיקת תשובה ידנית.

        Args:
            clue: ההגדרה

        Returns:
            True אם הצליח
        """
        if clue.id not in self.manual_answers:
            return False

        # הסרה מהנעולים
        for cell in clue.answer_cells:
            self.locked_cells.discard(cell)

        # הסרה מהגריד
        self.solution.remove_answer(clue)

        # הסרה מהמעקב
        del self.manual_answers[clue.id]
        self._placement_stack = [(c, a, m) for c, a, m in self._placement_stack if c.id != clue.id]

        # עדכון התקדמות
        self.progress.solved_clues -= 1
        self.progress.manual_clues -= 1

        return True

    def _can_backtrack_clue(self, clue: ClueEntry) -> bool:
        """בדיקה אם אפשר לעשות backtrack להגדרה"""
        return clue.id not in self.manual_answers

    def _is_cell_locked(self, row: int, col: int) -> bool:
        """בדיקה אם משבצת נעולה"""
        return (row, col) in self.locked_cells

    def pause(self) -> None:
        """עצירת הפתרון"""
        self._should_pause = True

    def resume(self) -> None:
        """המשך הפתרון"""
        self._should_pause = False

    def is_running(self) -> bool:
        """האם הפותר רץ"""
        return self._is_running

    def solve(
        self,
        progress_callback: Optional[Callable[[SolveProgress], None]] = None
    ) -> SolveProgress:
        """
        פותר את התשבץ עם callbacks לכל אות.

        Args:
            progress_callback: פונקציה לעדכון התקדמות (legacy)

        Returns:
            SolveProgress עם התוצאות
        """
        self._is_running = True
        self._should_pause = False
        self.progress.start_time = time.time()
        self.progress.status = SolveStatus.IN_PROGRESS

        # שלב ראשון: שבץ את כל התשובות הידניות
        for clue_id, answer in self.manual_answers.items():
            clue = self.clue_db.get_clue(clue_id)
            if clue and clue.id not in [c.id for c, _, _ in self._placement_stack]:
                self.solution.place_answer(clue, answer, confidence=1.0)
                self._placement_stack.append((clue, answer, True))

        # מיון הגדרות לפי קושי
        clues_to_solve = self._get_unsolved_clues()

        while clues_to_solve and self.progress.backtracks < self.max_backtracks:
            # בדיקת עצירה
            if self._should_pause:
                self.progress.status = SolveStatus.PAUSED
                self._is_running = False
                return self.progress

            # בחירת ההגדרה הבאה
            clue = clues_to_solve[0]
            self.progress.current_clue = clue.id

            # Callback: התחלת הגדרה
            if self.callbacks.on_clue_start:
                self.callbacks.on_clue_start(clue.id, clue.answer_cells)

            if progress_callback:
                progress_callback(self.progress)
            if self.callbacks.on_progress:
                self.callbacks.on_progress(self.progress)

            # עדכון אותיות ידועות מהמטריצה
            self._update_known_letters(clue)

            # קבלת תשובות אפשריות
            result = self.solver.solve_clue(clue)

            if result.error or not result.candidates:
                # אין תשובות - צריך backtrack
                if not self._backtrack():
                    self.progress.status = SolveStatus.STUCK
                    break
                clues_to_solve = self._get_unsolved_clues()
                continue

            # ניסיון לשבץ תשובה
            placed = False
            tried = self._tried_answers.get(clue.id, [])

            for answer, confidence in result.candidates:
                if answer in tried:
                    continue

                # בדיקת עצירה
                if self._should_pause:
                    self.progress.status = SolveStatus.PAUSED
                    self._is_running = False
                    return self.progress

                # ניסיון שיבוץ
                placement = self.solution.can_place(clue, answer)

                if placement.status == PlacementStatus.SUCCESS:
                    # שיבוץ מוצלח - אות אות!
                    self._place_answer_with_animation(clue, answer, confidence)
                    placed = True
                    break
                else:
                    tried.append(answer)

            self._tried_answers[clue.id] = tried

            if not placed:
                # לא הצלחנו לשבץ - backtrack
                if not self._backtrack():
                    self.progress.status = SolveStatus.STUCK
                    break

            # עדכון רשימת הגדרות
            clues_to_solve = self._get_unsolved_clues()

        # סיום
        self._is_running = False

        if self.progress.solved_clues == self.progress.total_clues:
            self.progress.status = SolveStatus.SOLVED
        elif self.progress.status == SolveStatus.IN_PROGRESS:
            self.progress.status = SolveStatus.STUCK

        # Callback: סיום
        if self.callbacks.on_completed:
            self.callbacks.on_completed(self.get_statistics())

        return self.progress

    def _get_unsolved_clues(self) -> List[ClueEntry]:
        """מחזיר הגדרות שעוד לא נפתרו (לא כולל ידניות)"""
        solved_ids = {c.id for c, _, _ in self._placement_stack}
        all_clues = self.clue_db.get_clues_sorted_by_difficulty()
        return [c for c in all_clues if c.id not in solved_ids]

    def _place_answer_with_animation(
        self,
        clue: ClueEntry,
        answer: str,
        confidence: float
    ) -> None:
        """שיבוץ תשובה עם animation - אות אחר אות"""

        # שיבוץ בגריד
        self.solution.place_answer(clue, answer, confidence)
        self._placement_stack.append((clue, answer, False))  # False = not manual

        # Callback לכל אות
        if self.callbacks.on_letter_placed:
            for i, (row, col) in enumerate(clue.answer_cells):
                letter = answer[i]
                self.callbacks.on_letter_placed(row, col, letter, i)

                # השהיה לאפקט ויזואלי
                if self.callbacks.letter_delay_ms > 0:
                    time.sleep(self.callbacks.letter_delay_ms / 1000.0)

                # בדיקת עצירה בין אותיות
                if self._should_pause:
                    break

        # עדכון אותיות ידועות להגדרות אחרות
        self.clue_db.update_known_letters(clue, answer)

        # Callback: הגדרה נפתרה
        if self.callbacks.on_clue_solved:
            self.callbacks.on_clue_solved(clue.id, answer, confidence)

        # תיעוד
        step = SolveStep(
            clue_id=clue.id,
            answer=answer,
            confidence=confidence,
            action="place",
            success=True,
            message=f"Placed '{answer}' for '{clue.text}'",
            is_manual=False
        )
        self.progress.steps.append(step)
        self.progress.solved_clues += 1

    def _update_known_letters(self, clue: ClueEntry) -> None:
        """מעדכן אותיות ידועות מהמטריצה"""
        known = self.solution.get_known_letters(clue.answer_cells)
        clue.known_letters = known

    def _backtrack(self) -> bool:
        """
        חוזר אחורה צעד אחד.
        לא נוגע בתשובות ידניות!

        Returns:
            True אם הצליח, False אם אין לאן לחזור
        """
        # מצא את ההגדרה האחרונה שאינה ידנית
        while self._placement_stack:
            clue, answer, is_manual = self._placement_stack[-1]

            if is_manual:
                # זו תשובה ידנית - לא נוגעים!
                # אין לאן לחזור
                return False

            # הסרת השיבוץ
            self._placement_stack.pop()
            break
        else:
            return False

        self.progress.backtracks += 1

        # אסוף אותיות שהוסרו (ל-callback)
        removed_letters = []
        for i, (row, col) in enumerate(clue.answer_cells):
            if not self._is_cell_locked(row, col):
                removed_letters.append((row, col, answer[i]))

        # הסרה מהגריד
        self.solution.remove_answer(clue)
        self.progress.solved_clues -= 1

        # סימון התשובה כ"נוסתה"
        if clue.id not in self._tried_answers:
            self._tried_answers[clue.id] = []
        self._tried_answers[clue.id].append(answer)

        # Callback: backtrack
        if self.callbacks.on_backtrack:
            self.callbacks.on_backtrack(clue.id, removed_letters)

        # תיעוד
        step = SolveStep(
            clue_id=clue.id,
            answer=answer,
            confidence=0,
            action="backtrack",
            success=True,
            message=f"Backtracked from '{answer}'"
        )
        self.progress.steps.append(step)

        return True

    def solve_step_by_step(self) -> Optional[SolveStep]:
        """
        מבצע צעד אחד בפתרון.
        מאפשר פתרון אינטראקטיבי.

        Returns:
            הצעד שבוצע, או None אם אין מה לעשות
        """
        clues_to_solve = self._get_unsolved_clues()

        if not clues_to_solve:
            return None

        clue = clues_to_solve[0]
        self._update_known_letters(clue)

        # Callback: התחלת הגדרה
        if self.callbacks.on_clue_start:
            self.callbacks.on_clue_start(clue.id, clue.answer_cells)

        result = self.solver.solve_clue(clue)

        if not result.candidates:
            if self._backtrack():
                return self.progress.steps[-1]
            return None

        tried = self._tried_answers.get(clue.id, [])

        for answer, confidence in result.candidates:
            if answer in tried:
                continue

            placement = self.solution.can_place(clue, answer)

            if placement.status == PlacementStatus.SUCCESS:
                self._place_answer_with_animation(clue, answer, confidence)
                return self.progress.steps[-1]

            tried.append(answer)

        self._tried_answers[clue.id] = tried

        if self._backtrack():
            return self.progress.steps[-1]

        return None

    def get_hint(self, clue: ClueEntry) -> Optional[Tuple[str, float]]:
        """
        מחזיר רמז (התשובה הכי סבירה) בלי לשבץ.

        Args:
            clue: ההגדרה

        Returns:
            (תשובה, ביטחון) או None
        """
        self._update_known_letters(clue)
        result = self.solver.solve_clue(clue)

        if result.candidates:
            return result.candidates[0]
        return None

    def manual_place(self, clue: ClueEntry, answer: str) -> bool:
        """
        שיבוץ ידני ע"י המשתמש - Wrapper ל-set_manual_answer.

        Args:
            clue: ההגדרה
            answer: התשובה

        Returns:
            True אם הצליח
        """
        return self.set_manual_answer(clue, answer)

    def set_manual_answer_by_id(self, clue_id: str, answer: str, answer_cells: Optional[List[Tuple[int, int]]] = None) -> bool:
        """
        הגדרת תשובה ידנית לפי ID - לשימוש מ-UI.

        Args:
            clue_id: מזהה ההגדרה
            answer: התשובה
            answer_cells: משבצות התשובה (אופציונלי)

        Returns:
            True אם הצליח
        """
        clue = self.clue_db.get_clue(clue_id)
        if clue:
            return self.set_manual_answer(clue, answer)
        return False

    def clear_manual_answer_by_id(self, clue_id: str) -> bool:
        """
        מחיקת תשובה ידנית לפי ID.

        Args:
            clue_id: מזהה ההגדרה

        Returns:
            True אם הצליח
        """
        clue = self.clue_db.get_clue(clue_id)
        if clue:
            return self.clear_manual_answer(clue)
        return False

    def get_statistics(self) -> Dict:
        """סטטיסטיקות הפתרון"""
        elapsed = time.time() - self.progress.start_time if self.progress.start_time else 0

        return {
            'status': self.progress.status.value,
            'total_clues': self.progress.total_clues,
            'solved_clues': self.progress.solved_clues,
            'manual_clues': self.progress.manual_clues,
            'completion_percentage': (
                self.progress.solved_clues / self.progress.total_clues * 100
                if self.progress.total_clues > 0 else 0
            ),
            'backtracks': self.progress.backtracks,
            'total_steps': len(self.progress.steps),
            'elapsed_time': elapsed,
            'grid_stats': self.solution.get_statistics()
        }

    def reset(self) -> None:
        """איפוס הפותר - כולל תשובות ידניות"""
        self.solution.clear()
        self._placement_stack = []
        self._tried_answers = {}
        self.manual_answers = {}
        self.locked_cells = set()
        self._should_pause = False
        self._is_running = False

        self.progress = SolveProgress(
            total_clues=len(self.clue_db.clues),
            solved_clues=0
        )

        # איפוס ההגדרות
        for clue in self.clue_db.clues:
            clue.chosen_answer = None
            clue.is_solved = False
            clue.known_letters = {}

    def reset_auto_only(self) -> None:
        """איפוס רק תשובות אוטומטיות - שומר על ידניות"""
        # שמור תשובות ידניות
        manual_backup = self.manual_answers.copy()
        locked_backup = self.locked_cells.copy()

        # איפוס מלא
        self.solution.clear()
        self._placement_stack = []
        self._tried_answers = {}
        self._should_pause = False
        self._is_running = False

        # שחזר תשובות ידניות
        self.manual_answers = manual_backup
        self.locked_cells = locked_backup

        # שבץ מחדש את הידניות
        for clue_id, answer in self.manual_answers.items():
            clue = self.clue_db.get_clue(clue_id)
            if clue:
                self.solution.place_answer(clue, answer, confidence=1.0)
                self._placement_stack.append((clue, answer, True))
                self.clue_db.update_known_letters(clue, answer)

        self.progress = SolveProgress(
            total_clues=len(self.clue_db.clues),
            solved_clues=len(self.manual_answers),
            manual_clues=len(self.manual_answers)
        )

        # איפוס הגדרות לא-ידניות
        for clue in self.clue_db.clues:
            if clue.id not in self.manual_answers:
                clue.chosen_answer = None
                clue.is_solved = False
