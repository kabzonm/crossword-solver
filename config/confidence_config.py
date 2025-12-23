"""
Confidence Scoring Configuration
הגדרות לחישוב ציוני ביטחון
"""

class ConfidenceConfig:
    """הגדרות לחישוב ציונים"""

    # Weights for overall confidence calculation
    WEIGHTS = {
        'ocr': 0.5,      # 50% משקל ל-OCR
        'arrow': 0.3,    # 30% משקל לחץ
        'quality': 0.2   # 20% משקל לאיכות תמונה
    }

    # Thresholds for confidence levels
    THRESHOLDS = {
        'HIGH': 0.85,    # 0.85-1.0 = HIGH confidence
        'MEDIUM': 0.65   # 0.65-0.85 = MEDIUM, <0.65 = LOW
    }

    # Image quality metrics weights
    QUALITY_WEIGHTS = {
        'sharpness': 0.4,
        'contrast': 0.3,
        'brightness': 0.2,
        'noise': 0.1
    }

    # Quality thresholds
    QUALITY_THRESHOLDS = {
        'sharpness_min': 100,      # Laplacian variance
        'contrast_min': 0.3,       # Michelson contrast
        'brightness_min': 50,      # Mean intensity
        'brightness_max': 200,
        'noise_max': 0.15          # Noise ratio
    }

    # OCR specific
    OCR_MIN_CONFIDENCE = 0.5
    OCR_WORD_LENGTH_BONUS = 0.05  # בונוס למילים ארוכות

    # Arrow specific
    ARROW_MIN_CONFIDENCE = 0.6
    ARROW_POSITION_BONUS = 0.1  # בונוס אם החץ במיקום צפוי
