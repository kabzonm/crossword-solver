"""
Stats Panel Component
פאנל סטטיסטיקות בזמן אמת
"""

import streamlit as st
import time
from typing import Optional
from ui.solver_state import SolverUIState, SolverMode


class StatsPanel:
    """
    סטטיסטיקות בזמן אמת של הפתרון.

    מציג:
    - Progress bar עם אחוזים
    - שעון (זמן שעבר)
    - נפתרו: X/Y
    - הוכנסו ידנית: Z
    - Backtracks: N
    - ביטחון ממוצע: XX%
    """

    def __init__(self, state: SolverUIState):
        self.state = state

    def render(self) -> None:
        """רינדור פאנל הסטטיסטיקות"""

        st.markdown("#### סטטיסטיקות")

        # Progress bar
        completion = self.state.get_completion_percentage()
        st.progress(completion / 100, text=f"{completion:.1f}% הושלם")

        # Stats in columns
        col1, col2 = st.columns(2)

        with col1:
            # Solved count
            st.metric(
                label="נפתרו",
                value=f"{self.state.solved_clues}/{self.state.total_clues}"
            )

            # Manual count
            st.metric(
                label="הוכנסו ידנית",
                value=str(self.state.manual_clues),
                delta=None
            )

        with col2:
            # Backtracks
            st.metric(
                label="Backtracks",
                value=str(self.state.backtracks),
                delta=None
            )

            # Average confidence
            confidence_str = f"{self.state.avg_confidence:.0f}%" if self.state.avg_confidence > 0 else "-"
            st.metric(
                label="ביטחון ממוצע",
                value=confidence_str
            )

        # Timer
        if self.state.mode != SolverMode.IDLE and self.state.start_time > 0:
            elapsed = time.time() - self.state.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            st.markdown(f"**זמן:** {minutes:02d}:{seconds:02d}")

        # Messages
        if self.state.error_message:
            st.error(self.state.error_message)

        if self.state.success_message:
            st.success(self.state.success_message)

    def render_compact(self) -> None:
        """רינדור מצומצם של סטטיסטיקות"""

        completion = self.state.get_completion_percentage()

        # Single line stats
        stats_text = f"נפתרו: {self.state.solved_clues}/{self.state.total_clues}"
        if self.state.manual_clues > 0:
            stats_text += f" | ידניים: {self.state.manual_clues}"
        if self.state.backtracks > 0:
            stats_text += f" | חזרות: {self.state.backtracks}"
        if self.state.avg_confidence > 0:
            stats_text += f" | ביטחון: {self.state.avg_confidence:.0f}%"

        st.caption(stats_text)


class CompletionSummary:
    """
    סיכום בסיום הפתרון
    """

    def __init__(self, state: SolverUIState):
        self.state = state

    def render(self) -> None:
        """רינדור סיכום סופי"""

        if self.state.mode != SolverMode.COMPLETED:
            return

        st.markdown("### סיכום פתרון")

        # Calculate total time
        if self.state.start_time > 0:
            elapsed = time.time() - self.state.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
        else:
            time_str = "לא ידוע"

        # Summary metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("סה\"כ נפתרו", f"{self.state.solved_clues}/{self.state.total_clues}")

        with col2:
            st.metric("הוכנסו ידנית", str(self.state.manual_clues))

        with col3:
            st.metric("זמן פתרון", time_str)

        # Additional stats
        if self.state.backtracks > 0:
            st.info(f"המערכת ביצעה {self.state.backtracks} חזרות אחורה (backtracks)")

        if self.state.avg_confidence > 0:
            confidence_label = "גבוה" if self.state.avg_confidence >= 80 else "בינוני" if self.state.avg_confidence >= 60 else "נמוך"
            st.info(f"ביטחון ממוצע: {self.state.avg_confidence:.1f}% ({confidence_label})")

        # Success message
        completion = self.state.get_completion_percentage()
        if completion == 100:
            st.success("התשבץ נפתר במלואו!")
        elif completion >= 80:
            st.warning(f"התשבץ נפתר חלקית ({completion:.0f}%)")
        else:
            st.error(f"הפתרון נתקע על {completion:.0f}%")


def render_stats_panel(state: SolverUIState, compact: bool = False) -> None:
    """פונקציית עזר לרינדור פאנל הסטטיסטיקות"""
    panel = StatsPanel(state)
    if compact:
        panel.render_compact()
    else:
        panel.render()


def render_completion_summary(state: SolverUIState) -> None:
    """פונקציית עזר לרינדור סיכום"""
    summary = CompletionSummary(state)
    summary.render()
