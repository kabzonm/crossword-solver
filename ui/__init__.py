"""
UI Components for Interactive Solver
רכיבי ממשק משתמש לפותר האינטראקטיבי
"""

from ui.solver_state import (
    SolverUIState,
    SolverMode,
    ClueStatus,
    CellStatus,
    STATUS_ICONS,
    STATUS_COLORS,
    CELL_COLORS
)
from ui.control_bar import ControlBar, render_control_bar
from ui.crossword_grid import CrosswordGridDisplay, render_crossword_grid
from ui.clues_table import CluesTableDisplay, render_clues_table
from ui.manual_edit_panel import ManualEditPanel, render_manual_edit_panel
from ui.stats_panel import StatsPanel, render_stats_panel, render_completion_summary
from ui.solver_view import SolverView, SolverViewConfig, render_solver_view

__all__ = [
    # State
    'SolverUIState',
    'SolverMode',
    'ClueStatus',
    'CellStatus',
    'STATUS_ICONS',
    'STATUS_COLORS',
    'CELL_COLORS',
    # Components
    'ControlBar',
    'CrosswordGridDisplay',
    'CluesTableDisplay',
    'ManualEditPanel',
    'StatsPanel',
    # Main View
    'SolverView',
    'SolverViewConfig',
    # Render functions
    'render_control_bar',
    'render_crossword_grid',
    'render_clues_table',
    'render_manual_edit_panel',
    'render_stats_panel',
    'render_completion_summary',
    'render_solver_view',
]
