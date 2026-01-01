"""
Cloud Services Configuration
הגדרות לשירותי ענן - Google Cloud Vision ו-GPT-4o
"""

import os
from dataclasses import dataclass, field
from typing import Optional


def _load_api_key_from_file(filename: str, silent: bool = False) -> Optional[str]:
    """טעינת API key מקובץ בתיקיית הפרויקט"""
    import os

    # חיפוש הקובץ בתיקיות אפשריות
    possible_paths = [
        filename,  # תיקייה נוכחית
        os.path.join(os.path.dirname(__file__), '..', filename),  # תיקיית הפרויקט
        os.path.join(os.path.dirname(__file__), '..', '..', filename),  # שתי רמות למעלה
    ]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    key = f.read().strip()
                    # הסרת גרשיים מיותרות אם יש
                    key = key.strip('"\'')
                    if key:
                        if not silent:
                            print(f"[OK] Loaded API key from {path}")
                        return key
            except Exception as e:
                if not silent:
                    print(f"Warning: Could not read {path}: {e}")

    return None


@dataclass
class GoogleVisionConfig:
    """הגדרות Google Cloud Vision API"""

    # API Credentials
    # אפשרות 1: משתנה סביבה עם נתיב לקובץ JSON
    credentials_path: Optional[str] = field(
        default_factory=lambda: os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    )

    # אפשרות 2: API Key מקובץ או ממשתנה סביבה
    api_key: Optional[str] = field(
        default_factory=lambda: (
            _load_api_key_from_file('google_vision_api.txt') or
            _load_api_key_from_file('services/google_vision_api.txt') or
            os.environ.get('GOOGLE_VISION_API_KEY')
        )
    )

    # הגדרות API
    max_results: int = 10  # מספר תוצאות מקסימלי לכל תמונה
    language_hints: list = field(default_factory=lambda: ['he', 'iw'])  # עברית

    # Batch settings
    batch_size: int = 16  # כמה תמונות לשלוח בבקשה אחת

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0  # שניות


@dataclass
class ClaudeVisionConfig:
    """הגדרות Claude Vision API (לא בשימוש - עברנו ל-GPT)"""

    # API Key - מקובץ או ממשתנה סביבה
    api_key: Optional[str] = field(
        default_factory=lambda: (
            _load_api_key_from_file('claude_api.txt') or
            os.environ.get('ANTHROPIC_API_KEY')
        )
    )

    # Model settings
    model: str = "claude-sonnet-4-20250514"  # מודל מומלץ - מאזן בין דיוק לעלות
    max_tokens: int = 1024
    temperature: float = 0.1  # נמוך לתוצאות עקביות

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class GPTVisionConfig:
    """הגדרות GPT-4o Vision API (לא בשימוש - עברנו ל-Gemini)"""

    # API Key - מקובץ או ממשתנה סביבה (silent=True כי לא בשימוש)
    api_key: Optional[str] = field(
        default_factory=lambda: (
            _load_api_key_from_file('openai_api.txt', silent=True) or
            _load_api_key_from_file('services/openai_api.txt', silent=True) or
            os.environ.get('OPENAI_API_KEY')
        )
    )

    # Model settings
    model: str = "gpt-5.2"  # GPT-5.2 - המודל המתקדם ביותר של OpenAI
    max_tokens: int = 1024
    temperature: float = 0.1  # נמוך לתוצאות עקביות

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class GeminiVisionConfig:
    """הגדרות Google Gemini 3 Pro Vision API"""

    # API Key - משתמש באותו API Key כמו Google Vision
    api_key: Optional[str] = field(
        default_factory=lambda: (
            _load_api_key_from_file('google_vision_api.txt') or
            _load_api_key_from_file('services/google_vision_api.txt') or
            os.environ.get('GOOGLE_API_KEY') or
            os.environ.get('GOOGLE_VISION_API_KEY')
        )
    )

    # Model settings
    model: str = "gemini-3-pro-preview"  # Gemini 3 Pro - המודל המתקדם ביותר של Google
    max_tokens: int = 16384  # הגדלנו עוד יותר כי thinking צורך הרבה טוקנים
    temperature: float = 0.1  # נמוך לתוצאות עקביות
    thinking_budget: int = 512  # הקטנו - מספיק לחשיבה בסיסית, משאיר יותר ל-output

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class CloudServicesConfig:
    """הגדרות כלליות לשירותי ענן"""

    # בחירת מנועים
    text_ocr_provider: str = "google"  # "google" או "tesseract"
    arrow_detector_provider: str = "gemini"  # "gemini", "gpt", "claude" או "template"

    # Fallback - מושבת! רוצים רק Gemini
    enable_fallback: bool = False  # השבתת fallback לגמרי
    fallback_on_error: bool = False  # לא להשתמש ב-Template Matching גם בשגיאה
    fallback_on_low_confidence: bool = False  # לא להשתמש ב-Template Matching גם ב-confidence נמוך
    fallback_confidence_threshold: float = 0.0  # סף 0 = לא משנה

    # Sub-configs
    google: GoogleVisionConfig = field(default_factory=GoogleVisionConfig)
    claude: ClaudeVisionConfig = field(default_factory=ClaudeVisionConfig)
    gpt: GPTVisionConfig = field(default_factory=GPTVisionConfig)
    gemini: GeminiVisionConfig = field(default_factory=GeminiVisionConfig)

    # Debug
    debug_mode: bool = False
    save_debug_images: bool = False
    debug_output_dir: str = "debug/"


# Singleton instance
_config_instance: Optional[CloudServicesConfig] = None


def get_cloud_config() -> CloudServicesConfig:
    """Get or create the cloud services config singleton"""
    global _config_instance
    if _config_instance is None:
        _config_instance = CloudServicesConfig()
    return _config_instance


def set_cloud_config(config: CloudServicesConfig) -> None:
    """Set the cloud services config singleton"""
    global _config_instance
    _config_instance = config
