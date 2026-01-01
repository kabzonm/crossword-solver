"""
Manual Edit Panel Component
פאנל עריכה ידנית של תשובות
"""

import streamlit as st
from typing import Optional, Callable, Dict, Any, List, Tuple
from ui.solver_state import SolverUIState, SolverMode, ClueStatus


class ManualEditPanel:
    """
    פאנל לעריכת תשובות ידנית.

    מוצג רק במצב PAUSED כשנבחרה הגדרה.

    מציג:
    - טקסט ההגדרה
    - אורך התשובה הנדרש
    - אותיות ידועות (מהצלבות)
    - שדה קלט לתשובה
    - [שמור] [בטל]

    וולידציה:
    - אורך התשובה חייב להיות תואם
    - אותיות ידועות חייבות להתאים
    """

    def __init__(
        self,
        state: SolverUIState,
        clue_data: Optional[Dict[str, Any]] = None,  # {id, text, answer_length, answer_cells, known_letters}
        on_save: Optional[Callable[[str, str], None]] = None,  # (clue_id, answer)
        on_cancel: Optional[Callable[[], None]] = None,
        on_clear: Optional[Callable[[str], None]] = None  # Clear manual answer
    ):
        self.state = state
        self.clue_data = clue_data
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.on_clear = on_clear

    def render(self) -> None:
        """רינדור פאנל העריכה"""

        # Only show in PAUSED mode with a selected clue
        if self.state.mode != SolverMode.PAUSED:
            return

        if not self.state.selected_clue_id or not self.clue_data:
            st.info("בחר הגדרה מהטבלה לעריכה ידנית")
            return

        clue_id = self.clue_data.get('id')
        clue_text = self.clue_data.get('text', '')
        answer_length = self.clue_data.get('answer_length', 0)
        known_letters = self.clue_data.get('known_letters', {})  # {position: letter}
        current_answer = self.state.clue_answers.get(clue_id, '')

        st.markdown("#### עריכה ידנית")

        # Clue info
        st.markdown(f"**הגדרה:** {clue_text}")
        st.markdown(f"**אורך נדרש:** {answer_length} אותיות")

        # Show known letters if any
        if known_letters:
            known_str = self._format_known_letters(known_letters, answer_length)
            st.markdown(f"**אותיות ידועות:** {known_str}")

        # Check if already manual
        is_manual = clue_id in self.state.manual_clue_ids

        # Input field
        default_value = current_answer if current_answer else ""
        answer_input = st.text_input(
            "תשובה:",
            value=default_value,
            max_chars=answer_length if answer_length > 0 else None,
            key=f"manual_input_{clue_id}",
            placeholder=self._format_known_letters(known_letters, answer_length)
        )

        # Validation
        validation_result = self._validate_answer(answer_input, answer_length, known_letters)

        if not validation_result['valid'] and answer_input:
            st.error(validation_result['message'])

        # Buttons
        col1, col2, col3 = st.columns(3)

        with col1:
            save_disabled = not validation_result['valid'] or not answer_input
            if st.button("✓ שמור", key="btn_save_manual", disabled=save_disabled, type="primary"):
                if self.on_save:
                    self.on_save(clue_id, answer_input)
                    st.success("התשובה נשמרה!")
                    st.rerun()

        with col2:
            if st.button("✗ בטל", key="btn_cancel_manual"):
                if self.on_cancel:
                    self.on_cancel()
                st.rerun()

        with col3:
            if is_manual:
                if st.button("🗑 מחק", key="btn_clear_manual"):
                    if self.on_clear:
                        self.on_clear(clue_id)
                        st.success("התשובה הידנית נמחקה")
                        st.rerun()

        # Show info about manual answers
        st.markdown("---")
        st.caption("💡 תשובות ידניות הופכות לאילוץ קבוע - המערכת לא תשנה אותן")

    def _format_known_letters(self, known_letters: Dict[int, str], length: int) -> str:
        """פורמט אותיות ידועות עם תווים ריקים"""
        result = []
        for i in range(length):
            if i in known_letters:
                result.append(known_letters[i])
            else:
                result.append("_")
        return "".join(result)

    def _validate_answer(
        self,
        answer: str,
        expected_length: int,
        known_letters: Dict[int, str]
    ) -> Dict[str, Any]:
        """וולידציה של התשובה"""

        if not answer:
            return {'valid': True, 'message': ''}

        # Check length
        if expected_length > 0 and len(answer) != expected_length:
            return {
                'valid': False,
                'message': f"אורך התשובה חייב להיות {expected_length} אותיות (נוכחי: {len(answer)})"
            }

        # Check known letters
        for pos, letter in known_letters.items():
            if pos < len(answer) and answer[pos] != letter:
                return {
                    'valid': False,
                    'message': f"האות במיקום {pos + 1} חייבת להיות '{letter}' (הוכנס: '{answer[pos]}')"
                }

        return {'valid': True, 'message': ''}


def render_manual_edit_panel(
    state: SolverUIState,
    clue_data: Optional[Dict[str, Any]] = None,
    on_save: Optional[Callable[[str, str], None]] = None,
    on_cancel: Optional[Callable[[], None]] = None,
    on_clear: Optional[Callable[[str], None]] = None
) -> None:
    """פונקציית עזר לרינדור פאנל העריכה"""
    panel = ManualEditPanel(state, clue_data, on_save, on_cancel, on_clear)
    panel.render()
