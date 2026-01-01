"""
Solver State Management
ניהול מצב ה-UI בזמן פתרון
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum


class SolverMode(Enum):
    """מצבי הפותר"""
    IDLE = "idle"           # לא התחיל
    RUNNING = "running"     # רץ אוטומטית
    PAUSED = "paused"       # עצור - מאפשר עריכה
    COMPLETED = "completed" # סיים


class ClueStatus(Enum):
    """סטטוס הגדרה"""
    PENDING = "pending"         # ⏳ ממתין
    IN_PROGRESS = "in_progress" # 🔄 בתהליך
    SOLVED = "solved"           # ✅ נפתר אוטומטית
    MANUAL = "manual"           # 🔒 הוכנס ידנית
    FAILED = "failed"           # ❌ נכשל
    BACKTRACKED = "backtracked" # ↩️ בוטל


# אייקונים לסטטוסים
STATUS_ICONS = {
    ClueStatus.PENDING: "⏳",
    ClueStatus.IN_PROGRESS: "🔄",
    ClueStatus.SOLVED: "✅",
    ClueStatus.MANUAL: "🔒",
    ClueStatus.FAILED: "❌",
    ClueStatus.BACKTRACKED: "↩️",
}

# צבעים לסטטוסים
STATUS_COLORS = {
    ClueStatus.PENDING: "#FFFFFF",      # לבן
    ClueStatus.IN_PROGRESS: "#FFEB3B",  # צהוב
    ClueStatus.SOLVED: "#C8E6C9",       # ירוק בהיר
    ClueStatus.MANUAL: "#BBDEFB",       # כחול בהיר
    ClueStatus.FAILED: "#FFCDD2",       # אדום בהיר
    ClueStatus.BACKTRACKED: "#FFE0B2",  # כתום בהיר
}


class CellStatus(Enum):
    """סטטוס משבצת בגריד"""
    EMPTY = "empty"           # ריקה
    SOLVING = "solving"       # בתהליך פתרון
    SOLVED = "solved"         # נפתרה אוטומטית
    MANUAL = "manual"         # הוכנסה ידנית
    CONFLICT = "conflict"     # יש קונפליקט
    HIGHLIGHTED = "highlighted"  # מודגשת (hover)


# צבעים למשבצות
CELL_COLORS = {
    'block': '#000000',       # שחור
    'clue': '#E0E0E0',        # אפור
    'empty': '#FFFFFF',       # לבן
    'solving': '#FFEB3B',     # צהוב
    'solved': '#C8E6C9',      # ירוק בהיר
    'manual': '#BBDEFB',      # כחול בהיר
    'conflict': '#FFCDD2',    # אדום בהיר
    'highlighted': '#FFF9C4', # צהוב בהיר
    'locked_border': '#1976D2' # כחול כהה (גבול למשבצת נעולה)
}


@dataclass
class SolverUIState:
    """מצב ה-UI בזמן פתרון"""

    # מצב כללי
    mode: SolverMode = SolverMode.IDLE
    selected_clue_id: Optional[str] = None  # הגדרה שנבחרה לעריכה

    # התקדמות
    total_clues: int = 0
    solved_clues: int = 0
    manual_clues: int = 0
    current_clue_id: Optional[str] = None

    # גריד
    grid_letters: Dict[Tuple[int, int], str] = field(default_factory=dict)
    highlighted_cells: List[Tuple[int, int]] = field(default_factory=list)
    manual_cells: Set[Tuple[int, int]] = field(default_factory=set)
    conflict_cells: List[Tuple[int, int]] = field(default_factory=list)
    solving_cells: List[Tuple[int, int]] = field(default_factory=list)

    # הגדרות
    clue_statuses: Dict[str, ClueStatus] = field(default_factory=dict)
    clue_answers: Dict[str, str] = field(default_factory=dict)
    manual_clue_ids: Set[str] = field(default_factory=set)

    # סטטיסטיקות
    start_time: float = 0.0
    backtracks: int = 0
    avg_confidence: float = 0.0

    # הודעות
    error_message: Optional[str] = None
    success_message: Optional[str] = None

    def reset(self) -> None:
        """איפוס המצב"""
        self.mode = SolverMode.IDLE
        self.selected_clue_id = None
        self.total_clues = 0
        self.solved_clues = 0
        self.manual_clues = 0
        self.current_clue_id = None
        self.grid_letters = {}
        self.highlighted_cells = []
        self.manual_cells = set()
        self.conflict_cells = []
        self.solving_cells = []
        self.clue_statuses = {}
        self.clue_answers = {}
        self.manual_clue_ids = set()
        self.start_time = 0.0
        self.backtracks = 0
        self.avg_confidence = 0.0
        self.error_message = None
        self.success_message = None

    def get_cell_status(self, row: int, col: int) -> CellStatus:
        """מחזיר סטטוס משבצת"""
        cell = (row, col)

        if cell in self.conflict_cells:
            return CellStatus.CONFLICT
        if cell in self.solving_cells:
            return CellStatus.SOLVING
        if cell in self.manual_cells:
            return CellStatus.MANUAL
        if cell in self.highlighted_cells:
            return CellStatus.HIGHLIGHTED
        if cell in self.grid_letters:
            return CellStatus.SOLVED
        return CellStatus.EMPTY

    def get_cell_color(self, row: int, col: int) -> str:
        """מחזיר צבע למשבצת"""
        status = self.get_cell_status(row, col)
        return CELL_COLORS.get(status.value, CELL_COLORS['empty'])

    def set_clue_status(self, clue_id: str, status: ClueStatus) -> None:
        """עדכון סטטוס הגדרה"""
        self.clue_statuses[clue_id] = status

    def get_clue_status(self, clue_id: str) -> ClueStatus:
        """קבלת סטטוס הגדרה"""
        return self.clue_statuses.get(clue_id, ClueStatus.PENDING)

    def add_letter(self, row: int, col: int, letter: str, is_manual: bool = False) -> None:
        """הוספת אות לגריד"""
        self.grid_letters[(row, col)] = letter
        if is_manual:
            self.manual_cells.add((row, col))

    def remove_letter(self, row: int, col: int) -> None:
        """הסרת אות מהגריד"""
        self.grid_letters.pop((row, col), None)
        self.manual_cells.discard((row, col))

    def highlight_cells(self, cells: List[Tuple[int, int]]) -> None:
        """הדגשת משבצות"""
        self.highlighted_cells = cells

    def clear_highlight(self) -> None:
        """ניקוי הדגשה"""
        self.highlighted_cells = []

    def set_solving_cells(self, cells: List[Tuple[int, int]]) -> None:
        """סימון משבצות בתהליך פתרון"""
        self.solving_cells = cells

    def clear_solving_cells(self) -> None:
        """ניקוי משבצות בתהליך"""
        self.solving_cells = []

    def get_completion_percentage(self) -> float:
        """אחוז השלמה"""
        if self.total_clues == 0:
            return 0.0
        return (self.solved_clues / self.total_clues) * 100

    def is_editable(self) -> bool:
        """האם אפשר לערוך (מצב PAUSED)"""
        return self.mode == SolverMode.PAUSED

    def can_start(self) -> bool:
        """האם אפשר להתחיל"""
        return self.mode == SolverMode.IDLE

    def can_pause(self) -> bool:
        """האם אפשר לעצור"""
        return self.mode == SolverMode.RUNNING

    def can_resume(self) -> bool:
        """האם אפשר להמשיך"""
        return self.mode == SolverMode.PAUSED
