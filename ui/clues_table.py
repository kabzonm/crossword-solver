"""
Clues Table Component
רכיב טבלת ההגדרות הדינמית
"""

import streamlit as st
from typing import Optional, Callable, List, Dict, Any
from ui.solver_state import SolverUIState, SolverMode, ClueStatus, STATUS_ICONS, STATUS_COLORS


class CluesTableDisplay:
    """
    טבלה דינמית של הגדרות עם תמיכה בעריכה.

    עמודות:
    - # (מספר סידורי)
    - הגדרה (טקסט)
    - תשובה (מתמלאת בזמן אמת)
    - סטטוס (אייקון)

    אינטראקציה:
    - לחיצה על שורה (במצב PAUSED) בוחרת לעריכה
    """

    def __init__(
        self,
        clues: List[Dict[str, Any]],  # רשימת הגדרות: {id, text, answer_length, ...}
        state: SolverUIState,
        on_clue_select: Optional[Callable[[str], None]] = None
    ):
        self.clues = clues
        self.state = state
        self.on_clue_select = on_clue_select

    def render(self) -> None:
        """רינדור טבלת ההגדרות"""

        if not self.clues:
            st.info("אין הגדרות להצגה")
            return

        st.markdown("#### הגדרות")

        # Header
        header_cols = st.columns([0.5, 3, 2, 1])
        with header_cols[0]:
            st.markdown("**#**")
        with header_cols[1]:
            st.markdown("**הגדרה**")
        with header_cols[2]:
            st.markdown("**תשובה**")
        with header_cols[3]:
            st.markdown("**סטטוס**")

        st.divider()

        # Container for scrollable table
        with st.container(height=300):
            for idx, clue in enumerate(self.clues):
                self._render_clue_row(idx, clue)

    def _render_clue_row(self, index: int, clue: Dict[str, Any]) -> None:
        """רינדור שורת הגדרה בודדת"""

        clue_id = clue.get('id', str(index))
        clue_text = clue.get('text', '')[:40]  # Truncate long text
        answer_length = clue.get('answer_length', 0)

        # Get status and answer from state
        status = self.state.get_clue_status(clue_id)
        answer = self.state.clue_answers.get(clue_id, '')

        # Determine if row is selected
        is_selected = self.state.selected_clue_id == clue_id
        is_current = self.state.current_clue_id == clue_id

        # Row styling
        row_style = self._get_row_style(status, is_selected, is_current)

        # Create clickable row (only in PAUSED mode)
        if self.state.mode == SolverMode.PAUSED:
            col1, col2, col3, col4 = st.columns([0.5, 3, 2, 1])

            with col1:
                st.markdown(f"{index + 1}")

            with col2:
                if st.button(
                    clue_text if clue_text else "(ריק)",
                    key=f"clue_btn_{clue_id}"
                ):
                    if self.on_clue_select:
                        self.on_clue_select(clue_id)

            with col3:
                # Show answer with placeholder for unknown letters
                display_answer = self._format_answer(answer, answer_length)
                st.markdown(display_answer)

            with col4:
                icon = STATUS_ICONS.get(status, "")
                st.markdown(icon)

        else:
            # Non-interactive row
            cols = st.columns([0.5, 3, 2, 1])

            with cols[0]:
                st.markdown(f"{index + 1}")

            with cols[1]:
                st.markdown(f"<span style='{row_style}'>{clue_text}</span>", unsafe_allow_html=True)

            with cols[2]:
                display_answer = self._format_answer(answer, answer_length)
                st.markdown(f"<span style='{row_style}'>{display_answer}</span>", unsafe_allow_html=True)

            with cols[3]:
                icon = STATUS_ICONS.get(status, "")
                st.markdown(icon)

    def _get_row_style(self, status: ClueStatus, is_selected: bool, is_current: bool) -> str:
        """מחזיר סגנון CSS לשורה"""

        bg_color = STATUS_COLORS.get(status, "#FFFFFF")

        if is_selected:
            return f"background-color: #E3F2FD; font-weight: bold; padding: 4px; border-radius: 4px; display: inline-block;"
        elif is_current:
            return f"background-color: {bg_color}; font-weight: bold; padding: 4px; border-radius: 4px; display: inline-block;"
        else:
            return f"background-color: {bg_color}; padding: 4px; border-radius: 4px; display: inline-block;"

    def _format_answer(self, answer: str, expected_length: int) -> str:
        """פורמט התשובה עם placeholder לאותיות חסרות"""

        if not answer:
            return "·" * expected_length if expected_length > 0 else ""

        # Pad with dots if answer is shorter than expected
        if len(answer) < expected_length:
            return answer + "·" * (expected_length - len(answer))

        return answer


def render_clues_table(
    clues: List[Dict[str, Any]],
    state: SolverUIState,
    on_clue_select: Optional[Callable[[str], None]] = None
) -> None:
    """פונקציית עזר לרינדור טבלת ההגדרות"""
    display = CluesTableDisplay(clues, state, on_clue_select)
    display.render()
