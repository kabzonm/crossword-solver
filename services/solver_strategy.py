"""
Solver Strategy - אסטרטגיית הפתרון החדשה

מיישם את האלגוריתם ב-4 שלבים:
1. Initial Query - שאילתא ראשונית לכל ההגדרות
2. Propagation - הפצת אילוצים ושיבוץ מילים
3. Re-Query - שאילתא מחודשת כשמתגלות 30%+ אותיות
4. Backtracking - חזרה אחורה כשנתקעים
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Callable
from enum import Enum

from models.clue_entry import ClueEntry
from services.clue_database import ClueDatabase
from services.solution_grid import SolutionGrid, PlacementStatus
from services.clue_solver import ClueSolver, SolverResult
from services.candidate_index import CandidateIndex, CandidateWord


class SolvePhase(Enum):
    """שלב בפתרון"""
    INITIAL_QUERY = "initial_query"
    PROPAGATION = "propagation"
    REQUERY = "requery"
    BACKTRACKING = "backtracking"
    COMPLETED = "completed"
    STUCK = "stuck"


class SolveStatus(Enum):
    """סטטוס פתרון"""
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    SOLVED = "solved"
    STUCK = "stuck"
    FAILED = "failed"


@dataclass
class ClueState:
    """מצב הגדרה בתהליך הפתרון"""
    clue: ClueEntry
    is_solved: bool = False
    placed_word: Optional[str] = None
    last_query_phase: int = 0
    known_letters_at_query: str = ""  # תבנית בזמן השאילתא האחרונה
    is_manual: bool = False  # האם הוכנס ידנית

    @property
    def current_pattern(self) -> str:
        """תבנית נוכחית מ-known_letters"""
        return self.clue.get_constraint_string()

    @property
    def needs_requery(self) -> bool:
        """האם צריך לשאול שוב"""
        if self.is_solved:
            return False
        current = self.current_pattern
        last = self.known_letters_at_query
        # צריך re-query אם יש אותיות חדשות
        return current != last and '_' in current


@dataclass
class SolverState:
    """מצב כללי של הפתרון"""
    clue_states: Dict[str, ClueState] = field(default_factory=dict)
    candidate_index: CandidateIndex = field(default_factory=CandidateIndex)
    current_phase: int = 1
    solve_phase: SolvePhase = SolvePhase.INITIAL_QUERY

    # מעקב אותיות
    total_solution_cells: int = 0
    letters_discovered: int = 0
    letters_since_query: int = 0

    # מעקב שיבוצים
    placement_stack: List[Tuple[str, str, bool]] = field(default_factory=list)  # (clue_id, word, is_manual)
    backtracks: int = 0

    # זמנים
    start_time: float = 0.0
    query_count: int = 0


@dataclass
class SolveProgress:
    """התקדמות הפתרון (לUI)"""
    total_clues: int = 0
    solved_clues: int = 0
    manual_clues: int = 0
    current_clue: Optional[str] = None
    backtracks: int = 0
    status: SolveStatus = SolveStatus.IN_PROGRESS
    phase: SolvePhase = SolvePhase.INITIAL_QUERY
    letters_discovered: int = 0
    total_letters: int = 0
    query_count: int = 0


@dataclass
class SolverCallbacks:
    """Callbacks לעדכוני UI"""
    on_clue_start: Optional[Callable[[str], None]] = None
    on_word_placed: Optional[Callable[[str, str, List[Tuple[int, int]]], None]] = None  # clue_id, word, cells
    on_backtrack: Optional[Callable[[str, str], None]] = None  # clue_id, removed_word
    on_progress: Optional[Callable[[SolveProgress], None]] = None
    on_phase_change: Optional[Callable[[SolvePhase], None]] = None
    on_requery: Optional[Callable[[int], None]] = None  # num_clues being requeried


class SolverStrategy:
    """
    אסטרטגיית הפתרון החדשה.

    עקרונות:
    1. שאילתא ראשונית לכל ההגדרות (batch)
    2. שיבוץ מילים שלמות בלבד (לא אותיות)
    3. עדיפות לפי confidence * clue_certainty
    4. Re-query אחרי 30% אותיות חדשות
    5. Backtracking כשנתקעים
    """

    REQUERY_THRESHOLD = 0.3  # 30% אותיות חדשות
    MAX_BACKTRACKS = 100
    HIGH_CONFIDENCE_THRESHOLD = 0.85  # מעל זה - שבץ מיד

    def __init__(
        self,
        clue_db: ClueDatabase,
        solution_grid: SolutionGrid,
        clue_solver: ClueSolver,
        max_backtracks: int = 100
    ):
        self.clue_db = clue_db
        self.solution = solution_grid
        self.solver = clue_solver
        self.max_backtracks = max_backtracks

        self.state = SolverState()
        self.callbacks = SolverCallbacks()

        # בקרת ריצה
        self._should_pause = False
        self._is_running = False

    def set_callbacks(self, callbacks: SolverCallbacks) -> None:
        """הגדרת callbacks"""
        self.callbacks = callbacks

    def initialize(self) -> None:
        """אתחול הסולבר"""
        self.state = SolverState()
        self.state.start_time = time.time()

        # יצירת ClueState לכל הגדרה
        for clue in self.clue_db.clues:
            self.state.clue_states[clue.id] = ClueState(clue=clue)

        # חישוב סך משבצות פתרון
        self.state.total_solution_cells = sum(
            clue.answer_length for clue in self.clue_db.clues
        ) // 2  # בערך - כי יש חפיפות

    def solve(self) -> SolveProgress:
        """
        פותר את התשבץ.

        Returns:
            SolveProgress עם התוצאות
        """
        self._is_running = True
        self._should_pause = False
        self.initialize()

        try:
            # Phase 1: Initial Query
            self._phase1_initial_query()

            # Main loop
            while not self._should_pause and self.state.solve_phase not in [
                SolvePhase.COMPLETED, SolvePhase.STUCK
            ]:
                if self.state.solve_phase == SolvePhase.PROPAGATION:
                    if not self._phase2_propagate():
                        # לא הצלחנו להתקדם
                        if self._should_requery():
                            self.state.solve_phase = SolvePhase.REQUERY
                        else:
                            self.state.solve_phase = SolvePhase.BACKTRACKING

                elif self.state.solve_phase == SolvePhase.REQUERY:
                    self._phase3_requery()
                    self.state.solve_phase = SolvePhase.PROPAGATION

                elif self.state.solve_phase == SolvePhase.BACKTRACKING:
                    if not self._phase4_backtrack():
                        self.state.solve_phase = SolvePhase.STUCK
                    else:
                        self.state.solve_phase = SolvePhase.PROPAGATION

                # בדיקה אם סיימנו
                if self._is_solved():
                    self.state.solve_phase = SolvePhase.COMPLETED

        finally:
            self._is_running = False

        return self._get_progress()

    def _phase1_initial_query(self) -> None:
        """Phase 1: שאילתא ראשונית לכל ההגדרות"""
        self.state.solve_phase = SolvePhase.INITIAL_QUERY
        self._notify_phase_change()

        # אסוף הגדרות לשאילתא
        clues_to_query = [
            state.clue for state in self.state.clue_states.values()
            if not state.is_manual and state.clue.answer_length > 0
        ]

        if not clues_to_query:
            self.state.solve_phase = SolvePhase.PROPAGATION
            return

        # שאילתא קבוצתית
        results = self.solver.solve_batch(clues_to_query)
        self.state.query_count += 1

        # בניית CandidateIndex
        for clue_id, result in results.items():
            if result.error or not result.candidates:
                continue

            clue_state = self.state.clue_states.get(clue_id)
            if not clue_state:
                continue

            # המרה ל-CandidateWord
            for answer, confidence in result.candidates:
                candidate = CandidateWord(
                    word=answer,
                    clue_id=clue_id,
                    confidence=confidence,
                    clue_certainty=getattr(result, 'clue_certainty', 0.5),
                    query_phase=1,
                    known_letters_snapshot=clue_state.current_pattern
                )
                self.state.candidate_index.add_candidate(candidate)

            # עדכון last_query
            clue_state.last_query_phase = 1
            clue_state.known_letters_at_query = clue_state.current_pattern

        self.state.solve_phase = SolvePhase.PROPAGATION
        self._notify_phase_change()

    def _phase2_propagate(self) -> bool:
        """
        Phase 2: הפצת אילוצים ושיבוץ.

        Returns:
            True אם הצלחנו לשבץ משהו, False אם נתקענו
        """
        # מצא את ההגדרה הטובה ביותר לשיבוץ
        best_clue_state, best_candidate = self._select_best_to_place()

        if not best_clue_state or not best_candidate:
            return False

        # שיבוץ המילה
        success = self._place_word(best_clue_state, best_candidate.word)

        return success

    def _select_best_to_place(self) -> Tuple[Optional[ClueState], Optional[CandidateWord]]:
        """
        בוחר את ההגדרה הטובה ביותר לשיבוץ.

        עדיפויות:
        1. הגדרה עם מועמד יחיד תקין
        2. הגדרה עם מועמד בביטחון גבוה מאוד (>0.85)
        3. הגדרה עם combined_score הגבוה ביותר
        """
        best_state = None
        best_candidate = None
        best_score = -1

        for clue_id, clue_state in self.state.clue_states.items():
            if clue_state.is_solved:
                continue

            pattern = clue_state.current_pattern
            candidates = self.state.candidate_index.get_valid_candidates_for_clue(
                clue_id, pattern
            )

            if not candidates:
                continue

            # עדיפות 1: מועמד יחיד
            if len(candidates) == 1:
                return clue_state, candidates[0]

            # עדיפות 2: ביטחון גבוה מאוד
            if candidates[0].confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                score = candidates[0].combined_score * 2  # בונוס
            else:
                score = candidates[0].combined_score

            if score > best_score:
                best_score = score
                best_state = clue_state
                best_candidate = candidates[0]

        return best_state, best_candidate

    def _place_word(self, clue_state: ClueState, word: str) -> bool:
        """
        משבץ מילה שלמה.

        Args:
            clue_state: מצב ההגדרה
            word: המילה לשיבוץ

        Returns:
            True אם הצליח
        """
        clue = clue_state.clue

        # בדיקת יכולת שיבוץ
        placement = self.solution.can_place(clue, word)
        if placement.status != PlacementStatus.SUCCESS:
            # לא ניתן לשבץ - סמן כנכשל
            self.state.candidate_index.mark_as_failed(clue.id, word)
            return False

        # שיבוץ בגריד
        self.solution.place_answer(clue, word, confidence=1.0)

        # עדכון מצב
        clue_state.is_solved = True
        clue_state.placed_word = word

        # הוספה לstack
        self.state.placement_stack.append((clue.id, word, False))

        # עדכון אותיות ידועות בהגדרות מצטלבות
        new_letters = self._update_intersecting_clues(clue, word)
        self.state.letters_discovered += new_letters
        self.state.letters_since_query += new_letters

        # סינון מועמדים לא תואמים
        self._filter_incompatible_candidates(clue, word)

        # Callback
        if self.callbacks.on_word_placed:
            self.callbacks.on_word_placed(clue.id, word, clue.answer_cells)

        self._notify_progress()

        return True

    def _update_intersecting_clues(self, placed_clue: ClueEntry, word: str) -> int:
        """
        מעדכן אותיות ידועות בהגדרות מצטלבות.

        Returns:
            מספר אותיות חדשות שנתגלו
        """
        new_letters = 0

        for i, (row, col) in enumerate(placed_clue.answer_cells):
            letter = word[i]

            # מצא הגדרות מצטלבות
            for other_clue in self.clue_db.get_clues_for_cell(row, col):
                if other_clue.id == placed_clue.id:
                    continue

                other_state = self.state.clue_states.get(other_clue.id)
                if not other_state or other_state.is_solved:
                    continue

                # מצא את האינדקס בהגדרה האחרת
                try:
                    other_idx = other_clue.answer_cells.index((row, col))
                    if other_idx not in other_clue.known_letters:
                        other_clue.known_letters[other_idx] = letter
                        new_letters += 1
                except ValueError:
                    pass

        return new_letters

    def _filter_incompatible_candidates(self, placed_clue: ClueEntry, word: str) -> None:
        """מסנן מועמדים שלא תואמים לאותיות החדשות"""
        for i, (row, col) in enumerate(placed_clue.answer_cells):
            letter = word[i]

            for other_clue in self.clue_db.get_clues_for_cell(row, col):
                if other_clue.id == placed_clue.id:
                    continue

                other_state = self.state.clue_states.get(other_clue.id)
                if not other_state or other_state.is_solved:
                    continue

                # מצא את האינדקס בהגדרה האחרת
                try:
                    other_idx = other_clue.answer_cells.index((row, col))
                    # סנן מועמדים שלא מתאימים
                    self.state.candidate_index.filter_by_letter(
                        other_clue.id, other_idx, letter, other_clue.answer_length
                    )
                except ValueError:
                    pass

    def _should_requery(self) -> bool:
        """בודק אם צריך Re-Query"""
        if self.state.total_solution_cells == 0:
            return False

        ratio = self.state.letters_since_query / self.state.total_solution_cells
        return ratio >= self.REQUERY_THRESHOLD

    def _phase3_requery(self) -> None:
        """Phase 3: שאילתא מחודשת"""
        self.state.solve_phase = SolvePhase.REQUERY
        self._notify_phase_change()

        # מצא הגדרות שצריכות re-query
        clues_to_requery = []
        for clue_id, clue_state in self.state.clue_states.items():
            if clue_state.is_solved:
                continue
            if clue_state.needs_requery:
                clues_to_requery.append(clue_state.clue)

        if not clues_to_requery:
            return

        # Callback
        if self.callbacks.on_requery:
            self.callbacks.on_requery(len(clues_to_requery))

        # שאילתא
        self.state.current_phase += 1
        results = self.solver.solve_batch(clues_to_requery)
        self.state.query_count += 1

        # מיזוג תוצאות
        for clue_id, result in results.items():
            if result.error or not result.candidates:
                continue

            clue_state = self.state.clue_states.get(clue_id)
            if not clue_state:
                continue

            # המרה ל-CandidateWord ומיזוג
            new_candidates = []
            for answer, confidence in result.candidates:
                candidate = CandidateWord(
                    word=answer,
                    clue_id=clue_id,
                    confidence=confidence,
                    clue_certainty=getattr(result, 'clue_certainty', 0.5),
                    query_phase=self.state.current_phase,
                    known_letters_snapshot=clue_state.current_pattern
                )
                new_candidates.append(candidate)

            self.state.candidate_index.merge_new_candidates(
                new_candidates, self.state.current_phase
            )

            # עדכון last_query
            clue_state.last_query_phase = self.state.current_phase
            clue_state.known_letters_at_query = clue_state.current_pattern

        # אפס מונה אותיות
        self.state.letters_since_query = 0

    def _phase4_backtrack(self) -> bool:
        """
        Phase 4: חזרה אחורה.

        Returns:
            True אם הצלחנו לעשות backtrack, False אם אין לאן
        """
        if self.state.backtracks >= self.max_backtracks:
            return False

        if not self.state.placement_stack:
            return False

        # מצא את השיבוץ האחרון שאינו ידני
        while self.state.placement_stack:
            clue_id, word, is_manual = self.state.placement_stack[-1]

            if is_manual:
                # לא נוגעים בידניים
                return False

            # הסרה מה-stack
            self.state.placement_stack.pop()
            break
        else:
            return False

        self.state.backtracks += 1

        # קבלת ההגדרה
        clue_state = self.state.clue_states.get(clue_id)
        if not clue_state:
            return False

        clue = clue_state.clue

        # הסרה מהגריד
        self.solution.remove_answer(clue)

        # עדכון מצב
        clue_state.is_solved = False
        clue_state.placed_word = None

        # סימון המילה כנכשלה
        self.state.candidate_index.mark_as_failed(clue_id, word)

        # עדכון known_letters בהגדרות מצטלבות (צריך לחשב מחדש)
        self._recalculate_known_letters()

        # Callback
        if self.callbacks.on_backtrack:
            self.callbacks.on_backtrack(clue_id, word)

        self._notify_progress()

        return True

    def _recalculate_known_letters(self) -> None:
        """מחשב מחדש את known_letters לכל ההגדרות"""
        # איפוס
        for clue in self.clue_db.clues:
            clue.known_letters = {}

        # עדכון מהגריד
        for clue_id, clue_state in self.state.clue_states.items():
            if not clue_state.is_solved:
                continue

            clue = clue_state.clue
            word = clue_state.placed_word

            if not word:
                continue

            # עדכון הצלבות
            for i, (row, col) in enumerate(clue.answer_cells):
                letter = word[i]

                for other_clue in self.clue_db.get_clues_for_cell(row, col):
                    if other_clue.id == clue.id:
                        continue

                    try:
                        other_idx = other_clue.answer_cells.index((row, col))
                        other_clue.known_letters[other_idx] = letter
                    except ValueError:
                        pass

    def _is_solved(self) -> bool:
        """בודק אם התשבץ נפתר"""
        return all(
            state.is_solved for state in self.state.clue_states.values()
            if state.clue.answer_length > 0
        )

    def _get_progress(self) -> SolveProgress:
        """מחזיר את מצב ההתקדמות"""
        solved = sum(1 for s in self.state.clue_states.values() if s.is_solved)
        manual = sum(1 for s in self.state.clue_states.values() if s.is_manual)
        total = len(self.state.clue_states)

        status = SolveStatus.IN_PROGRESS
        if self.state.solve_phase == SolvePhase.COMPLETED:
            status = SolveStatus.SOLVED
        elif self.state.solve_phase == SolvePhase.STUCK:
            status = SolveStatus.STUCK
        elif self._should_pause:
            status = SolveStatus.PAUSED

        return SolveProgress(
            total_clues=total,
            solved_clues=solved,
            manual_clues=manual,
            backtracks=self.state.backtracks,
            status=status,
            phase=self.state.solve_phase,
            letters_discovered=self.state.letters_discovered,
            total_letters=self.state.total_solution_cells,
            query_count=self.state.query_count
        )

    def _notify_progress(self) -> None:
        """מעדכן את ה-callback על התקדמות"""
        if self.callbacks.on_progress:
            self.callbacks.on_progress(self._get_progress())

    def _notify_phase_change(self) -> None:
        """מעדכן על שינוי שלב"""
        if self.callbacks.on_phase_change:
            self.callbacks.on_phase_change(self.state.solve_phase)

    # === Manual Answers ===

    def set_manual_answer(self, clue_id: str, word: str) -> bool:
        """
        הגדרת תשובה ידנית.

        Args:
            clue_id: מזהה ההגדרה
            word: התשובה

        Returns:
            True אם הצליח
        """
        clue_state = self.state.clue_states.get(clue_id)
        if not clue_state:
            return False

        clue = clue_state.clue

        # בדיקת אורך
        if len(word) != clue.answer_length:
            return False

        # בדיקת התאמה לתבנית
        if not clue.matches_answer(word):
            return False

        # שיבוץ
        self.solution.place_answer(clue, word, confidence=1.0)

        # עדכון מצב
        clue_state.is_solved = True
        clue_state.placed_word = word
        clue_state.is_manual = True

        # הוספה ל-stack
        self.state.placement_stack.append((clue_id, word, True))

        # עדכון הצלבות
        self._update_intersecting_clues(clue, word)
        self._filter_incompatible_candidates(clue, word)

        return True

    def clear_manual_answer(self, clue_id: str) -> bool:
        """מחיקת תשובה ידנית"""
        clue_state = self.state.clue_states.get(clue_id)
        if not clue_state or not clue_state.is_manual:
            return False

        clue = clue_state.clue

        # הסרה מהגריד
        self.solution.remove_answer(clue)

        # עדכון מצב
        clue_state.is_solved = False
        clue_state.placed_word = None
        clue_state.is_manual = False

        # הסרה מה-stack
        self.state.placement_stack = [
            (cid, w, m) for cid, w, m in self.state.placement_stack
            if cid != clue_id
        ]

        # עדכון known_letters
        self._recalculate_known_letters()

        return True

    # === Control ===

    def pause(self) -> None:
        """עצירת הפתרון"""
        self._should_pause = True

    def resume(self) -> SolveProgress:
        """המשך הפתרון"""
        self._should_pause = False
        return self.solve()

    def is_running(self) -> bool:
        """האם רץ"""
        return self._is_running

    def reset(self) -> None:
        """איפוס מלא"""
        self.state = SolverState()
        self.solution.clear()
        for clue in self.clue_db.clues:
            clue.known_letters = {}
            clue.chosen_answer = None
            clue.is_solved = False

    def get_statistics(self) -> Dict:
        """סטטיסטיקות"""
        progress = self._get_progress()
        elapsed = time.time() - self.state.start_time if self.state.start_time else 0

        return {
            'status': progress.status.value,
            'phase': progress.phase.value,
            'total_clues': progress.total_clues,
            'solved_clues': progress.solved_clues,
            'manual_clues': progress.manual_clues,
            'completion_percentage': (
                progress.solved_clues / progress.total_clues * 100
                if progress.total_clues > 0 else 0
            ),
            'backtracks': progress.backtracks,
            'query_count': progress.query_count,
            'letters_discovered': progress.letters_discovered,
            'elapsed_time': elapsed,
            'candidate_stats': self.state.candidate_index.get_statistics()
        }
