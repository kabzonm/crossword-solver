"""
Solver View - Main View Component
רכיב View מרכזי שמרכיב את כל הרכיבים

גרסה משופרת עם פתרון צעד-אחר-צעד (step-by-step solving)
לתאימות עם מודל הביצוע של Streamlit
"""

import streamlit as st
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from ui.solver_state import SolverUIState, SolverMode, ClueStatus
from ui.control_bar import render_control_bar
from ui.crossword_grid import render_crossword_grid
from ui.clues_table import render_clues_table
from ui.manual_edit_panel import render_manual_edit_panel
from ui.stats_panel import render_stats_panel, render_completion_summary


@dataclass
class SolverViewConfig:
    """הגדרות לתצוגת הפותר"""
    cell_size: int = 45
    letter_delay_ms: int = 150
    show_stats: bool = True
    show_manual_edit: bool = True


class SolverView:
    """
    View מרכזי לפותר התשבץ האינטראקטיבי.

    מרכיב:
    - ControlBar - כפתורי שליטה
    - CrosswordGrid - תצוגת הגריד
    - CluesTable - טבלת הגדרות
    - ManualEditPanel - פאנל עריכה ידנית
    - StatsPanel - סטטיסטיקות
    """

    def __init__(
        self,
        grid_data: List[List[Dict]],
        clues: List[Dict[str, Any]],
        puzzle_solver: Any,  # PuzzleSolver instance
        config: Optional[SolverViewConfig] = None
    ):
        self.grid_data = grid_data
        self.clues = clues
        self.solver = puzzle_solver
        self.config = config or SolverViewConfig()

        # Initialize or get state from session
        self._init_session_state()

    def _init_session_state(self) -> None:
        """אתחול session state"""

        if 'solver_ui_state' not in st.session_state:
            st.session_state.solver_ui_state = SolverUIState()

        if 'solver_instance' not in st.session_state:
            st.session_state.solver_instance = self.solver

        if 'is_solving' not in st.session_state:
            st.session_state.is_solving = False

    @property
    def state(self) -> SolverUIState:
        """גישה ל-state"""
        return st.session_state.solver_ui_state

    def render(self) -> None:
        """רינדור התצוגה המלאה"""

        # Update total clues count
        self.state.total_clues = len(self.clues)

        # Control bar
        render_control_bar(
            state=self.state,
            on_start=self._on_start,
            on_pause=self._on_pause,
            on_resume=self._on_resume,
            on_reset=self._on_reset,
            on_save=self._on_save
        )

        st.divider()

        # === Step-by-step solving ===
        # אם אנחנו במצב RUNNING, נבצע צעד אחד ונעדכן את ה-UI
        if self.state.mode == SolverMode.RUNNING and st.session_state.get('is_solving', False):
            self._execute_solving_step()

        # Main layout - two columns
        left_col, right_col = st.columns([1, 1])

        with left_col:
            # Crossword grid
            st.markdown("#### גריד התשבץ")
            render_crossword_grid(
                grid_data=self.grid_data,
                state=self.state,
                cell_size=self.config.cell_size
            )

        with right_col:
            # Clues table
            render_clues_table(
                clues=self.clues,
                state=self.state,
                on_clue_select=self._on_clue_select
            )

            # Manual edit panel (only in PAUSED mode)
            if self.state.mode == SolverMode.PAUSED and self.config.show_manual_edit:
                st.divider()
                selected_clue_data = self._get_selected_clue_data()
                render_manual_edit_panel(
                    state=self.state,
                    clue_data=selected_clue_data,
                    on_save=self._on_manual_save,
                    on_cancel=self._on_manual_cancel,
                    on_clear=self._on_manual_clear
                )

            # Stats panel
            if self.config.show_stats:
                st.divider()
                render_stats_panel(self.state)

        # Completion summary (when done)
        if self.state.mode == SolverMode.COMPLETED:
            st.divider()
            render_completion_summary(self.state)

    def _execute_solving_step(self) -> None:
        """
        מבצע צעד אחד בפתרון ומעדכן את ה-UI.

        כל צעד פותר הגדרה אחת ואז עושה rerun כדי לעדכן את התצוגה.
        """
        if not self.solver:
            self.state.error_message = "הפותר לא מאותחל"
            self.state.mode = SolverMode.PAUSED
            st.session_state.is_solving = False
            return

        # הצגת סטטוס נוכחי
        status_placeholder = st.empty()
        status_placeholder.info(f"🔄 פותר... ({self.state.solved_clues}/{self.state.total_clues})")

        try:
            # ביצוע צעד אחד
            step = self.solver.solve_step_by_step()

            if step is None:
                # אין יותר מה לפתור
                if self.state.solved_clues >= self.state.total_clues:
                    self.state.mode = SolverMode.COMPLETED
                    self.state.success_message = "התשבץ נפתר בהצלחה! 🎉"
                else:
                    self.state.mode = SolverMode.PAUSED
                    self.state.error_message = f"הפותר נתקע. נפתרו {self.state.solved_clues}/{self.state.total_clues}"

                st.session_state.is_solving = False
                status_placeholder.empty()
                return

            # עדכון ה-UI State מבוסס על הצעד
            if step.action == "place" and step.success:
                # הצעד כבר עדכן את ה-state דרך הקולבקים
                status_placeholder.success(f"✓ נפתר: {step.answer}")
            elif step.action == "backtrack":
                status_placeholder.warning(f"↩️ Backtrack מ-{step.answer}")

            # המתנה קצרה לאפקט ויזואלי
            time.sleep(0.3)
            status_placeholder.empty()

            # Rerun לעדכון התצוגה ולביצוע הצעד הבא
            st.rerun()

        except Exception as e:
            self.state.error_message = f"שגיאה בפתרון: {str(e)}"
            self.state.mode = SolverMode.PAUSED
            st.session_state.is_solving = False
            status_placeholder.error(f"❌ שגיאה: {str(e)}")

    def _get_selected_clue_data(self) -> Optional[Dict[str, Any]]:
        """מחזיר נתוני ההגדרה הנבחרת"""
        if not self.state.selected_clue_id:
            return None

        for clue in self.clues:
            if clue.get('id') == self.state.selected_clue_id:
                # Add known letters from grid
                answer_cells = clue.get('answer_cells', [])
                known_letters = {}
                for i, (row, col) in enumerate(answer_cells):
                    letter = self.state.grid_letters.get((row, col))
                    if letter and (row, col) not in self.state.manual_cells:
                        # Only add as known if it's from another clue (not this one's manual entry)
                        known_letters[i] = letter

                return {
                    **clue,
                    'known_letters': known_letters
                }

        return None

    # ===== Event Handlers =====

    def _on_start(self) -> None:
        """התחלת פתרון - מפעיל מצב step-by-step"""
        self.state.mode = SolverMode.RUNNING
        self.state.start_time = time.time()
        self.state.error_message = None
        self.state.success_message = None

        # Initialize clue statuses
        for clue in self.clues:
            clue_id = clue.get('id', '')
            if clue_id not in self.state.manual_clue_ids:
                self.state.clue_statuses[clue_id] = ClueStatus.PENDING

        # Set up solver callbacks
        if self.solver:
            callbacks = self.create_solver_callbacks()
            self.solver.set_callbacks(callbacks)

        st.session_state.is_solving = True
        st.session_state.solving_step_pending = True  # סימון שיש צעד להריץ

    def _on_pause(self) -> None:
        """עצירת פתרון"""
        self.state.mode = SolverMode.PAUSED
        st.session_state.is_solving = False
        self.state.success_message = "הפתרון הושהה. לחץ 'המשך' להמשיך."

    def _on_resume(self) -> None:
        """המשך פתרון"""
        self.state.mode = SolverMode.RUNNING
        self.state.selected_clue_id = None
        self.state.error_message = None
        self.state.success_message = None

        # Set up solver callbacks if needed
        if self.solver:
            callbacks = self.create_solver_callbacks()
            self.solver.set_callbacks(callbacks)

        st.session_state.is_solving = True

    def _on_reset(self) -> None:
        """איפוס"""
        # Keep manual answers option
        keep_manual = st.session_state.get('keep_manual_on_reset', False)

        if keep_manual:
            # Reset only auto-solved
            self.state.mode = SolverMode.IDLE
            self.state.solved_clues = self.state.manual_clues

            # Remove non-manual letters
            for pos in list(self.state.grid_letters.keys()):
                if pos not in self.state.manual_cells:
                    del self.state.grid_letters[pos]

            # Reset non-manual clue statuses
            for clue_id in self.state.clue_statuses:
                if clue_id not in self.state.manual_clue_ids:
                    self.state.clue_statuses[clue_id] = ClueStatus.PENDING
        else:
            # Full reset
            self.state.reset()

        self.state.selected_clue_id = None
        self.state.error_message = None
        self.state.success_message = None

        if self.solver:
            if keep_manual:
                self.solver.reset_auto_only()
            else:
                self.solver.reset()

        st.session_state.is_solving = False

    def _on_save(self) -> None:
        """שמירת תוצאות"""
        # Generate results for download
        results = {
            'solved_clues': self.state.solved_clues,
            'total_clues': self.state.total_clues,
            'manual_clues': self.state.manual_clues,
            'answers': self.state.clue_answers,
            'grid_letters': {f"{k[0]},{k[1]}": v for k, v in self.state.grid_letters.items()}
        }

        import json
        json_str = json.dumps(results, ensure_ascii=False, indent=2)

        st.download_button(
            label="הורד תוצאות (JSON)",
            data=json_str,
            file_name="crossword_solution.json",
            mime="application/json"
        )

    def _on_clue_select(self, clue_id: str) -> None:
        """בחירת הגדרה לעריכה"""
        self.state.selected_clue_id = clue_id

        # Highlight the clue's cells
        for clue in self.clues:
            if clue.get('id') == clue_id:
                answer_cells = clue.get('answer_cells', [])
                self.state.highlight_cells(answer_cells)
                break

    def _on_manual_save(self, clue_id: str, answer: str) -> None:
        """שמירת תשובה ידנית"""

        # Find clue data
        clue_data = None
        for clue in self.clues:
            if clue.get('id') == clue_id:
                clue_data = clue
                break

        if not clue_data:
            self.state.error_message = "לא נמצאה ההגדרה"
            return

        # Update state
        self.state.clue_answers[clue_id] = answer
        self.state.clue_statuses[clue_id] = ClueStatus.MANUAL
        self.state.manual_clue_ids.add(clue_id)

        # Add letters to grid
        answer_cells = clue_data.get('answer_cells', [])
        for i, (row, col) in enumerate(answer_cells):
            if i < len(answer):
                self.state.add_letter(row, col, answer[i], is_manual=True)

        # Update counts
        if clue_id not in [c.get('id') for c in self.clues if self.state.clue_statuses.get(c.get('id')) == ClueStatus.SOLVED]:
            self.state.solved_clues += 1
        self.state.manual_clues = len(self.state.manual_clue_ids)

        # Update solver
        if self.solver:
            self.solver.set_manual_answer_by_id(clue_id, answer, answer_cells)

        # Clear selection
        self.state.selected_clue_id = None
        self.state.clear_highlight()
        self.state.success_message = f"התשובה '{answer}' נשמרה"

    def _on_manual_cancel(self) -> None:
        """ביטול עריכה ידנית"""
        self.state.selected_clue_id = None
        self.state.clear_highlight()

    def _on_manual_clear(self, clue_id: str) -> None:
        """מחיקת תשובה ידנית"""

        # Find clue data
        clue_data = None
        for clue in self.clues:
            if clue.get('id') == clue_id:
                clue_data = clue
                break

        if not clue_data:
            return

        # Remove from state
        self.state.clue_answers.pop(clue_id, None)
        self.state.clue_statuses[clue_id] = ClueStatus.PENDING
        self.state.manual_clue_ids.discard(clue_id)

        # Remove letters from grid
        answer_cells = clue_data.get('answer_cells', [])
        for row, col in answer_cells:
            self.state.remove_letter(row, col)
            self.state.manual_cells.discard((row, col))

        # Update counts
        self.state.solved_clues = max(0, self.state.solved_clues - 1)
        self.state.manual_clues = len(self.state.manual_clue_ids)

        # Update solver
        if self.solver:
            self.solver.clear_manual_answer_by_id(clue_id)

        # Clear selection
        self.state.selected_clue_id = None
        self.state.clear_highlight()

    # ===== Callbacks for Solver =====

    def create_solver_callbacks(self) -> Dict[str, Any]:
        """יצירת callbacks לפותר"""
        from services.puzzle_solver import SolverCallbacks

        return SolverCallbacks(
            on_clue_start=self._callback_clue_start,
            on_letter_placed=self._callback_letter_placed,
            on_clue_solved=self._callback_clue_solved,
            on_backtrack=self._callback_backtrack,
            on_progress=self._callback_progress,
            on_completed=self._callback_completed,
            letter_delay_ms=self.config.letter_delay_ms
        )

    def _callback_clue_start(self, clue_id: str, cells: List[Tuple[int, int]]) -> None:
        """Callback: התחלת פתרון הגדרה"""
        self.state.current_clue_id = clue_id
        self.state.clue_statuses[clue_id] = ClueStatus.IN_PROGRESS
        self.state.set_solving_cells(cells)

    def _callback_letter_placed(self, row: int, col: int, letter: str, index: int) -> None:
        """Callback: שיבוץ אות"""
        self.state.add_letter(row, col, letter, is_manual=False)

    def _callback_clue_solved(self, clue_id: str, answer: str, confidence: float) -> None:
        """Callback: הגדרה נפתרה"""
        self.state.clue_statuses[clue_id] = ClueStatus.SOLVED
        self.state.clue_answers[clue_id] = answer
        self.state.solved_clues += 1
        self.state.clear_solving_cells()

        # Update average confidence
        current_total = self.state.avg_confidence * (self.state.solved_clues - 1)
        self.state.avg_confidence = (current_total + confidence * 100) / self.state.solved_clues

    def _callback_backtrack(self, clue_id: str, removed_letters: List[Tuple[int, int, str]]) -> None:
        """Callback: backtrack"""
        self.state.clue_statuses[clue_id] = ClueStatus.BACKTRACKED
        self.state.backtracks += 1

        # Remove letters
        for row, col, _ in removed_letters:
            self.state.remove_letter(row, col)

        # Update solved count
        if clue_id in self.state.clue_answers:
            del self.state.clue_answers[clue_id]
            self.state.solved_clues = max(0, self.state.solved_clues - 1)

    def _callback_progress(self, progress: Any) -> None:
        """Callback: התקדמות כללית"""
        pass  # State is updated through other callbacks

    def _callback_completed(self, stats: Dict[str, Any]) -> None:
        """Callback: סיום"""
        self.state.mode = SolverMode.COMPLETED
        self.state.clear_solving_cells()
        st.session_state.is_solving = False


def render_solver_view(
    grid_data: List[List[Dict]],
    clues: List[Dict[str, Any]],
    puzzle_solver: Any,
    config: Optional[SolverViewConfig] = None
) -> None:
    """פונקציית עזר לרינדור התצוגה"""
    view = SolverView(grid_data, clues, puzzle_solver, config)
    view.render()
