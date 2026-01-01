"""
Cloud Services Configuration
הגדרות לשירותי ענן - Google Cloud Vision ו-Claude
"""

import os
from dataclasses import dataclass, field
from typing import Optional


def _load_api_key_from_file(filename: str) -> Optional[str]:
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
                        print(f"[OK] Loaded API key from {path}")
                        return key
            except Exception as e:
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
    """הגדרות Claude Vision API"""

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
class CloudServicesConfig:
    """הגדרות כלליות לשירותי ענן"""

    # בחירת מנועים
    text_ocr_provider: str = "google"  # "google" או "tesseract"
    arrow_detector_provider: str = "claude"  # "claude" או "template"

    # Fallback
    enable_fallback: bool = True
    fallback_on_error: bool = True
    fallback_on_low_confidence: bool = True
    fallback_confidence_threshold: float = 0.5

    # Sub-configs
    google: GoogleVisionConfig = field(default_factory=GoogleVisionConfig)
    claude: ClaudeVisionConfig = field(default_factory=ClaudeVisionConfig)

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
