"""Database manager for SQLite connection and schema management."""

import sqlite3
import os
from pathlib import Path
from typing import Optional


class DatabaseManager:
    """Manages SQLite database connection and schema."""

    CURRENT_SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default: data/crosswords.db relative to project root
            project_root = Path(__file__).parent.parent
            db_path = project_root / "data" / "crosswords.db"

        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database directory and tables if they don't exist."""
        # Create directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create tables
        conn = self.get_connection()
        cursor = conn.cursor()

        # Puzzles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS puzzles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rows INTEGER NOT NULL,
                cols INTEGER NOT NULL,
                schema_version INTEGER DEFAULT 1
            )
        ''')

        # Cells table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                puzzle_id INTEGER NOT NULL,
                row INTEGER NOT NULL,
                col INTEGER NOT NULL,
                cell_type TEXT NOT NULL,
                FOREIGN KEY (puzzle_id) REFERENCES puzzles(id) ON DELETE CASCADE,
                UNIQUE(puzzle_id, row, col)
            )
        ''')

        # Clues table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                puzzle_id INTEGER NOT NULL,
                cell_id INTEGER NOT NULL,
                clue_id TEXT NOT NULL,
                text TEXT NOT NULL,
                zone TEXT DEFAULT 'full',
                confidence REAL DEFAULT 0.0,
                ocr_confidence REAL DEFAULT 0.0,
                arrow_confidence REAL DEFAULT 0.0,
                arrow_direction TEXT,
                arrow_position TEXT,
                exit_side TEXT,
                arrowhead_direction TEXT,
                answer_start_row INTEGER,
                answer_start_col INTEGER,
                writing_direction TEXT,
                answer_length INTEGER DEFAULT 0,
                FOREIGN KEY (puzzle_id) REFERENCES puzzles(id) ON DELETE CASCADE,
                FOREIGN KEY (cell_id) REFERENCES cells(id) ON DELETE CASCADE,
                UNIQUE(puzzle_id, clue_id)
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cells_puzzle ON cells(puzzle_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cells_position ON cells(puzzle_id, row, col)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clues_puzzle ON clues(puzzle_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clues_cell ON clues(cell_id)')

        conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection (creates new one each time to avoid locking)."""
        # סגירת connection קודם אם קיים
        if self._connection is not None:
            try:
                self._connection.close()
            except:
                pass
            self._connection = None

        self._connection = sqlite3.connect(str(self.db_path), timeout=10)
        self._connection.row_factory = sqlite3.Row
        # Enable foreign keys
        self._connection.execute('PRAGMA foreign_keys = ON')
        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
