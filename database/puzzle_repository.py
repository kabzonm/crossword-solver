"""Repository for puzzle CRUD operations."""

from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from .db_manager import DatabaseManager
from models.grid import GridMatrix, Cell, CellType, SplitType


class PuzzleRepository:
    """CRUD operations for puzzles."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize repository.

        Args:
            db_manager: Database manager instance. If None, creates default one.
        """
        self.db = db_manager or DatabaseManager()

    def save_puzzle(
        self,
        name: str,
        grid: GridMatrix
    ) -> int:
        """
        Save a new puzzle to database.

        Args:
            name: Unique name for the puzzle
            grid: GridMatrix with analyzed cells

        Returns:
            Puzzle ID

        Raises:
            ValueError: If puzzle with this name already exists
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Check if name exists
        cursor.execute('SELECT id FROM puzzles WHERE name = ?', (name,))
        if cursor.fetchone():
            raise ValueError(f"תשבץ בשם '{name}' כבר קיים")

        # Insert puzzle
        cursor.execute('''
            INSERT INTO puzzles (name, rows, cols, schema_version)
            VALUES (?, ?, ?, ?)
        ''', (name, grid.rows, grid.cols, DatabaseManager.CURRENT_SCHEMA_VERSION))

        puzzle_id = cursor.lastrowid

        # Insert cells and clues
        for r in range(grid.rows):
            for c in range(grid.cols):
                cell = grid.matrix[r][c]
                cell_id = self._save_cell(cursor, puzzle_id, cell)

                # Save clues if this is a CLUE cell with parsed_clues
                if hasattr(cell, 'parsed_clues') and cell.parsed_clues:
                    for i, clue_data in enumerate(cell.parsed_clues):
                        self._save_clue(cursor, puzzle_id, cell_id, r, c, i, clue_data)

        conn.commit()
        self.db.close()
        return puzzle_id

    def _save_cell(self, cursor, puzzle_id: int, cell: Cell) -> int:
        """Save a single cell and return its ID."""
        cursor.execute('''
            INSERT INTO cells (puzzle_id, row, col, cell_type)
            VALUES (?, ?, ?, ?)
        ''', (puzzle_id, cell.row, cell.col, cell.type.value))

        return cursor.lastrowid

    def _save_clue(
        self,
        cursor,
        puzzle_id: int,
        cell_id: int,
        row: int,
        col: int,
        index: int,
        clue_data: dict
    ):
        """Save a single clue."""
        zone = clue_data.get('zone', 'full')
        clue_id = f"clue_{row}_{col}_{zone}_{index}"

        # Extract answer_start tuple
        answer_start = clue_data.get('answer_start')
        start_row = answer_start[0] if answer_start else None
        start_col = answer_start[1] if answer_start else None

        cursor.execute('''
            INSERT INTO clues (
                puzzle_id, cell_id, clue_id, text, zone,
                confidence, ocr_confidence, arrow_confidence,
                arrow_direction, arrow_position, exit_side, arrowhead_direction,
                answer_start_row, answer_start_col, writing_direction, answer_length
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            puzzle_id,
            cell_id,
            clue_id,
            clue_data.get('text', ''),
            zone,
            clue_data.get('confidence', 0.0),
            clue_data.get('ocr_confidence', 0.0),
            clue_data.get('arrow_confidence', 0.0),
            clue_data.get('path', ''),  # arrow_direction stored as 'path'
            clue_data.get('arrow_position', ''),
            clue_data.get('exit_side', ''),
            clue_data.get('arrowhead_direction', ''),
            start_row,
            start_col,
            clue_data.get('writing_direction', ''),
            clue_data.get('answer_length', 0)
        ))

    def load_puzzle(self, name: str) -> GridMatrix:
        """
        Load a puzzle by name.

        Args:
            name: Puzzle name

        Returns:
            GridMatrix with all cell data

        Raises:
            ValueError: If puzzle not found
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get puzzle
        cursor.execute('SELECT * FROM puzzles WHERE name = ?', (name,))
        puzzle_row = cursor.fetchone()

        if not puzzle_row:
            raise ValueError(f"תשבץ בשם '{name}' לא נמצא")

        return self._load_puzzle_data(cursor, puzzle_row)

    def load_puzzle_by_id(self, puzzle_id: int) -> GridMatrix:
        """
        Load a puzzle by ID.

        Args:
            puzzle_id: Puzzle ID

        Returns:
            GridMatrix with all cell data

        Raises:
            ValueError: If puzzle not found
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM puzzles WHERE id = ?', (puzzle_id,))
        puzzle_row = cursor.fetchone()

        if not puzzle_row:
            raise ValueError(f"תשבץ עם ID {puzzle_id} לא נמצא")

        return self._load_puzzle_data(cursor, puzzle_row)

    def _load_puzzle_data(self, cursor, puzzle_row) -> GridMatrix:
        """Load puzzle data from database rows."""
        puzzle_id = puzzle_row['id']
        rows = puzzle_row['rows']
        cols = puzzle_row['cols']

        # Create grid
        grid = GridMatrix(rows=rows, cols=cols)
        grid.initialize_grid()

        # Load cells
        cursor.execute('''
            SELECT * FROM cells WHERE puzzle_id = ? ORDER BY row, col
        ''', (puzzle_id,))

        cell_map = {}  # cell_id -> (row, col)
        for cell_row in cursor.fetchall():
            r, c = cell_row['row'], cell_row['col']
            cell = grid.matrix[r][c]
            cell.type = CellType(cell_row['cell_type'])
            cell_map[cell_row['id']] = (r, c)

        # Load clues
        cursor.execute('''
            SELECT * FROM clues WHERE puzzle_id = ? ORDER BY cell_id, clue_id
        ''', (puzzle_id,))

        for clue_row in cursor.fetchall():
            cell_id = clue_row['cell_id']
            if cell_id not in cell_map:
                continue

            r, c = cell_map[cell_id]
            cell = grid.matrix[r][c]

            # Initialize parsed_clues if needed
            if not hasattr(cell, 'parsed_clues') or cell.parsed_clues is None:
                cell.parsed_clues = []

            # Build clue dict
            answer_start = None
            if clue_row['answer_start_row'] is not None and clue_row['answer_start_col'] is not None:
                answer_start = (clue_row['answer_start_row'], clue_row['answer_start_col'])

            clue_data = {
                'text': clue_row['text'],
                'zone': clue_row['zone'],
                'confidence': clue_row['confidence'],
                'ocr_confidence': clue_row['ocr_confidence'],
                'arrow_confidence': clue_row['arrow_confidence'],
                'path': clue_row['arrow_direction'],
                'arrow_position': clue_row['arrow_position'],
                'exit_side': clue_row['exit_side'],
                'arrowhead_direction': clue_row['arrowhead_direction'],
                'answer_start': answer_start,
                'writing_direction': clue_row['writing_direction'],
                'answer_length': clue_row['answer_length']
            }

            cell.parsed_clues.append(clue_data)

        return grid

    def list_puzzles(self) -> List[Dict]:
        """
        Get list of all saved puzzles.

        Returns:
            List of puzzle metadata dicts with keys:
            - id, name, created_at, updated_at, rows, cols
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, created_at, updated_at, rows, cols
            FROM puzzles
            ORDER BY updated_at DESC
        ''')

        return [dict(row) for row in cursor.fetchall()]

    def delete_puzzle(self, puzzle_id: int) -> bool:
        """
        Delete a puzzle by ID.

        Args:
            puzzle_id: Puzzle ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM puzzles WHERE id = ?', (puzzle_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        self.db.close()
        return deleted

    def puzzle_exists(self, name: str) -> bool:
        """Check if a puzzle with given name exists."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT 1 FROM puzzles WHERE name = ?', (name,))
        return cursor.fetchone() is not None

    def get_puzzle_count(self) -> int:
        """Get total number of saved puzzles."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM puzzles')
        return cursor.fetchone()[0]
