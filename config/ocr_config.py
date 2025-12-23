"""
OCR Engine Configuration
מגדיר את הפרמטרים של מנועי ה-OCR
"""

class OcrConfig:
    """הגדרות למנועי OCR"""

    # Engine selection
    # אפשרויות: 'tesseract' (מומלץ לעברית), 'easyocr', 'paddleocr'
    PRIMARY_ENGINE = 'tesseract'  # Tesseract הוא היחיד שתומך בעברית!
    FALLBACK_ENGINE = None  # אין fallback כרגע

    # Thresholds
    CONFIDENCE_THRESHOLD = 0.7  # אם confidence נמוך מזה, משתמש ב-fallback
    MIN_TEXT_LENGTH = 1  # אורך מינימלי של טקסט
    MAX_TEXT_LENGTH = 100  # אורך מקסימלי

    # GPU settings
    GPU_ENABLED = True

    # Languages
    LANGUAGES = ['he']  # עברית (לא בשימוש ב-Tesseract)

    # Tesseract specific
    TESSERACT_LANG = 'heb'  # קוד עברית ב-Tesseract
    TESSERACT_PATH = None  # None = חפש אוטומטית, או נתיב מלא
    TESSERACT_CONFIG = '--psm 6'  # Page segmentation mode: 6 = uniform block of text

    # EasyOCR specific (לא תומך בעברית!)
    EASYOCR_DETAIL = 1  # 0=simple, 1=detailed
    EASYOCR_PARAGRAPH = False
    EASYOCR_BATCH_SIZE = 4

    # PaddleOCR specific (לא תומך בעברית!)
    PADDLEOCR_USE_ANGLE_CLS = True
    PADDLEOCR_USE_GPU = True
    PADDLEOCR_SHOW_LOG = False

    # Preprocessing
    ENHANCE_CONTRAST = True
    DENOISE = True
    SHARPEN = True
