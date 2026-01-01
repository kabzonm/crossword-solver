"""
Crossword Grid Display Component
רכיב תצוגת גריד התשבץ האינטראקטיבי
"""

import streamlit as st
from typing import Optional, Callable, List, Tuple, Dict
from ui.solver_state import SolverUIState, SolverMode, CellStatus, CELL_COLORS
from models.grid import CellType


class CrosswordGridDisplay:
    """
    תצוגת גריד אינטראקטיבית.

    סוגי משבצות:
    - BLOCK = רקע שחור
    - CLUE = רקע אפור עם טקסט קטן
    - SOLUTION:
        - ריקה = רקע לבן
        - בתהליך = רקע צהוב
        - פתורה אוטומטית = רקע ירוק בהיר
        - פתורה ידנית = רקע כחול בהיר + גבול
        - קונפליקט = רקע אדום

    אינטראקציה:
    - לחיצה על משבצת SOLUTION (במצב PAUSED) פותח עריכה
    """

    def __init__(
        self,
        grid_data: List[List[Dict]],  # מידע על כל משבצת (type, text, etc.)
        state: SolverUIState,
        on_cell_click: Optional[Callable[[int, int], None]] = None,
        cell_size: int = 45
    ):
        self.grid_data = grid_data
        self.state = state
        self.on_cell_click = on_cell_click
        self.cell_size = cell_size

    def render(self) -> None:
        """רינדור הגריד"""

        if not self.grid_data:
            st.info("אין נתוני גריד להצגה")
            return

        rows = len(self.grid_data)
        cols = len(self.grid_data[0]) if rows > 0 else 0

        # Create HTML grid
        html = self._generate_grid_html(rows, cols)
        st.markdown(html, unsafe_allow_html=True)

        # If in PAUSED mode, show clickable interface
        if self.state.mode == SolverMode.PAUSED:
            st.caption("לחץ על הגדרה בטבלה למטה לעריכה ידנית")

    def _generate_grid_html(self, rows: int, cols: int) -> str:
        """יצירת HTML לגריד"""

        cell_size = self.cell_size
        font_size = int(cell_size * 0.5)
        clue_font_size = int(cell_size * 0.2)

        # CSS styles
        css = f"""
        <style>
        .crossword-grid {{
            display: grid;
            grid-template-columns: repeat({cols}, {cell_size}px);
            gap: 1px;
            background-color: #333;
            padding: 1px;
            direction: rtl;
            width: fit-content;
            margin: 0 auto;
        }}
        .grid-cell {{
            width: {cell_size}px;
            height: {cell_size}px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: {font_size}px;
            font-weight: bold;
            position: relative;
            box-sizing: border-box;
        }}
        .cell-block {{
            background-color: {CELL_COLORS['block']};
        }}
        .cell-clue {{
            background-color: {CELL_COLORS['clue']};
            font-size: {clue_font_size}px;
            padding: 2px;
            text-align: center;
            overflow: hidden;
            word-break: break-all;
            line-height: 1.1;
        }}
        .cell-empty {{
            background-color: {CELL_COLORS['empty']};
        }}
        .cell-solving {{
            background-color: {CELL_COLORS['solving']};
            animation: pulse 0.5s ease-in-out infinite alternate;
        }}
        .cell-solved {{
            background-color: {CELL_COLORS['solved']};
        }}
        .cell-manual {{
            background-color: {CELL_COLORS['manual']};
            border: 2px solid {CELL_COLORS['locked_border']};
        }}
        .cell-conflict {{
            background-color: {CELL_COLORS['conflict']};
        }}
        .cell-highlighted {{
            background-color: {CELL_COLORS['highlighted']};
        }}
        .lock-icon {{
            position: absolute;
            top: 2px;
            left: 2px;
            font-size: 10px;
        }}
        @keyframes pulse {{
            from {{ opacity: 0.7; }}
            to {{ opacity: 1; }}
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: scale(0.5); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}
        .letter-new {{
            animation: fadeIn 0.2s ease-out;
        }}
        </style>
        """

        # Generate grid cells
        cells_html = ""
        for row in range(rows):
            for col in range(cols):
                cell_html = self._render_cell(row, col)
                cells_html += cell_html

        html = f"""
        {css}
        <div class="crossword-grid">
            {cells_html}
        </div>
        """

        return html

    def _render_cell(self, row: int, col: int) -> str:
        """רינדור משבצת בודדת"""

        cell_data = self.grid_data[row][col]
        cell_type = cell_data.get('type', 'empty')

        # Block cell
        if cell_type == 'block' or cell_type == CellType.BLOCK:
            return '<div class="grid-cell cell-block"></div>'

        # Clue cell
        if cell_type == 'clue' or cell_type == CellType.CLUE:
            clue_text = cell_data.get('text', '')[:20]  # Truncate long text
            return f'<div class="grid-cell cell-clue">{clue_text}</div>'

        # Solution cell - check state
        letter = self.state.grid_letters.get((row, col), '')
        cell_status = self.state.get_cell_status(row, col)

        css_class = self._get_cell_css_class(cell_status)
        lock_icon = '<span class="lock-icon">🔒</span>' if cell_status == CellStatus.MANUAL else ''

        return f'<div class="grid-cell {css_class}">{lock_icon}{letter}</div>'

    def _get_cell_css_class(self, status: CellStatus) -> str:
        """מחזיר CSS class לפי סטטוס"""
        mapping = {
            CellStatus.EMPTY: 'cell-empty',
            CellStatus.SOLVING: 'cell-solving',
            CellStatus.SOLVED: 'cell-solved',
            CellStatus.MANUAL: 'cell-manual',
            CellStatus.CONFLICT: 'cell-conflict',
            CellStatus.HIGHLIGHTED: 'cell-highlighted',
        }
        return mapping.get(status, 'cell-empty')


def render_crossword_grid(
    grid_data: List[List[Dict]],
    state: SolverUIState,
    on_cell_click: Optional[Callable[[int, int], None]] = None,
    cell_size: int = 45
) -> None:
    """פונקציית עזר לרינדור הגריד"""
    display = CrosswordGridDisplay(grid_data, state, on_cell_click, cell_size)
    display.render()
