"""
Control Bar Component
סרגל בקרה - כפתורי שליטה בפותר
"""

import streamlit as st
from typing import Callable, Optional
from ui.solver_state import SolverMode, SolverUIState


class ControlBar:
    """
    סרגל בקרה לפותר התשבץ.

    כפתורים לפי מצב:
    - IDLE: [התחל]
    - RUNNING: [עצור]
    - PAUSED: [המשך] [אפס]
    - COMPLETED: [אפס] [שמור]
    """

    def __init__(
        self,
        state: SolverUIState,
        on_start: Optional[Callable[[], None]] = None,
        on_pause: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
        on_reset: Optional[Callable[[], None]] = None,
        on_save: Optional[Callable[[], None]] = None
    ):
        self.state = state
        self.on_start = on_start
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_reset = on_reset
        self.on_save = on_save

    def render(self) -> None:
        """רינדור סרגל הבקרה"""

        # Header with progress
        completion = self.state.get_completion_percentage()
        if self.state.mode == SolverMode.IDLE:
            st.markdown("### פותר תשבץ")
        else:
            st.markdown(f"### פותר תשבץ - {completion:.0f}% הושלם")

        # Control buttons in columns
        cols = st.columns([1, 1, 1, 2])

        with cols[0]:
            self._render_primary_button()

        with cols[1]:
            self._render_secondary_button()

        with cols[2]:
            self._render_reset_button()

        with cols[3]:
            self._render_timer()

    def _render_primary_button(self) -> None:
        """כפתור ראשי - התחל/עצור/המשך"""

        if self.state.mode == SolverMode.IDLE:
            if st.button("▶ התחל", key="btn_start", type="primary"):
                if self.on_start:
                    self.on_start()

        elif self.state.mode == SolverMode.RUNNING:
            if st.button("⏸ עצור", key="btn_pause", type="secondary"):
                if self.on_pause:
                    self.on_pause()

        elif self.state.mode == SolverMode.PAUSED:
            if st.button("▶ המשך", key="btn_resume", type="primary"):
                if self.on_resume:
                    self.on_resume()

        elif self.state.mode == SolverMode.COMPLETED:
            if st.button("💾 שמור", key="btn_save", type="primary"):
                if self.on_save:
                    self.on_save()

    def _render_secondary_button(self) -> None:
        """כפתור משני - שמירה במצב COMPLETED"""

        if self.state.mode == SolverMode.COMPLETED:
            # Show download button for results
            pass  # Will be implemented with actual save functionality

    def _render_reset_button(self) -> None:
        """כפתור איפוס"""

        if self.state.mode != SolverMode.IDLE:
            if st.button("↻ אפס", key="btn_reset"):
                if self.on_reset:
                    self.on_reset()

    def _render_timer(self) -> None:
        """הצגת זמן"""
        import time

        if self.state.mode == SolverMode.IDLE:
            st.markdown("זמן: --:--")
        else:
            elapsed = time.time() - self.state.start_time if self.state.start_time > 0 else 0
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            st.markdown(f"זמן: {minutes:02d}:{seconds:02d}")


def render_control_bar(
    state: SolverUIState,
    on_start: Optional[Callable[[], None]] = None,
    on_pause: Optional[Callable[[], None]] = None,
    on_resume: Optional[Callable[[], None]] = None,
    on_reset: Optional[Callable[[], None]] = None,
    on_save: Optional[Callable[[], None]] = None
) -> None:
    """פונקציית עזר לרינדור סרגל הבקרה"""
    bar = ControlBar(state, on_start, on_pause, on_resume, on_reset, on_save)
    bar.render()
