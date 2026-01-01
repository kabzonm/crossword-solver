"""
Recognition Result Models
מודלי נתונים לתוצאות הזיהוי
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum
import numpy as np


class ConfidenceLevel(Enum):
    """רמות ביטחון"""
    HIGH = "HIGH"      # 0.85-1.0
    MEDIUM = "MEDIUM"  # 0.65-0.85
    LOW = "LOW"        # 0.0-0.65


@dataclass
class OcrResult:
    """תוצאת OCR למשבצת"""
    text: str
    confidence: float
    engine_used: str  # 'easyocr' or 'paddleocr'
    bbox: List[Tuple[int, int]] = field(default_factory=list)  # bounding boxes של כל תו
    fallback_triggered: bool = False
    processing_time: float = 0.0
    raw_result: Optional[any] = None  # תוצאה גולמית מהמנוע


@dataclass
class ArrowResult:
    """תוצאת זיהוי חץ"""
    direction: str  # 'straight-down', 'start-left-turn-down', etc.
    confidence: float
    position: str = "unknown"  # מיקום החץ בתמונה: top-right, bottom-left, center, etc.
    match_location: Tuple[int, int] = (0, 0)
    scale_used: float = 1.0
    processing_time: float = 0.0
    template_matched: Optional[str] = None  # שם התבנית שהתאימה


@dataclass
class ImageQualityMetrics:
    """מדדי איכות תמונה"""
    sharpness: float  # Laplacian variance
    contrast: float   # Michelson contrast
    brightness: float # Mean intensity
    noise_level: float # Estimated SNR


@dataclass
class ConfidenceScore:
    """ציון ביטחון מצטבר"""
    overall: float
    ocr_confidence: float
    arrow_confidence: float
    image_quality: float
    level: ConfidenceLevel
    components: Dict[str, float] = field(default_factory=dict)


@dataclass
class CellRecognitionResult:
    """תוצאה מלאה למשבצת"""
    ocr_result: Optional[OcrResult] = None
    arrow_results: Optional[List[ArrowResult]] = None  # רשימה של עד 2 חצים
    confidence: Optional[ConfidenceScore] = None
    processing_time: float = 0.0
    cell_image: Optional[np.ndarray] = None  # לדיבוג - תמונה מדויקת לOCR
    arrow_image: Optional[np.ndarray] = None  # לדיבוג - תמונה מורחבת לזיהוי חצים
    error: Optional[str] = None  # הודעת שגיאה אם היתה
