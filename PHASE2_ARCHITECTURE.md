# מסמך ארכיטקטורה: אינטגרציית Google Cloud Vision + Claude Vision
## Crossword Solver - Phase 2 Architecture

**גרסה:** 2.0  
**תאריך:** דצמבר 2025  
**מטרה:** מסמך זה מיועד לביצוע על ידי Claude Code

---

## 1. תקציר השינוי

### המצב הנוכחי
- **OCR:** Tesseract עם תמיכה בעברית (דיוק ~60-70%)
- **חצים:** Template Matching עם 36 תבניות PNG
- **בעיה:** דיוק נמוך מאוד בזיהוי טקסט עברי

### המצב החדש
- **OCR לטקסט עברי:** Google Cloud Vision API (דיוק צפוי ~90-95%)
- **זיהוי חצים:** Claude Vision API (דיוק צפוי ~95-98%)
- **Fallback:** Tesseract משופר לעבודה offline

---

## 2. ארכיטקטורה חדשה

### 2.1 דיאגרמת זרימה

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                            (app.py - Streamlit)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OCR SERVICE                                     │
│                        (services/ocr_service_new.py)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RecognitionOrchestrator                           │   │
│  │  • בוחר אסטרטגיה לפי זמינות ותצורה                                   │   │
│  │  • מנהל fallback אוטומטי                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│   GOOGLE VISION SERVICE │ │   CLAUDE VISION SERVICE │ │   TESSERACT SERVICE     │
│   (google_vision_ocr.py)│ │   (claude_arrow_detect.)│ │   (ocr_engine_manager)  │
│                         │ │                         │ │                         │
│   • זיהוי טקסט עברי     │ │   • זיהוי כיוון חצים    │ │   • Fallback offline    │
│   • Batch API           │ │   • הבנת הקשר           │ │   • PSM 10 לתווים בודדים│
│   • ~$1.50/1000 תמונות  │ │   • ~$0.02/תשבץ         │ │   • חינם                │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BATCH PROCESSOR                                    │
│                      (services/batch_processor.py)                          │
│  • עיבוד מקבילי של תאים                                                     │
│  • שילוב תוצאות OCR + Arrow Detection                                       │
│  • Confidence Scoring                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GRID MATRIX                                     │
│                          (models/grid.py)                                   │
│  • CellRecognitionResult מעודכן לכל תא                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 חלוקת אחריות

| רכיב | תפקיד | קלט | פלט |
|------|-------|-----|-----|
| **GoogleVisionOcrService** | זיהוי טקסט עברי | תמונת תא (numpy) | `OcrResult` |
| **ClaudeArrowDetector** | זיהוי כיוון חץ | תמונת תא (numpy) | `ArrowResult` |
| **RecognitionOrchestrator** | תיאום ו-fallback | תמונה + config | תוצאה משולבת |
| **BatchProcessor** | עיבוד מקבילי | Grid + Image | Updated Grid |

---

## 3. קבצים לשינוי/יצירה

### 3.1 קבצים חדשים ליצירה

```
services/
├── google_vision_ocr.py      # NEW - Google Cloud Vision OCR
├── claude_arrow_detector.py  # NEW - Claude Vision לחצים
├── recognition_orchestrator.py # NEW - תיאום בין השירותים
└── api_config.py             # NEW - ניהול API keys

config/
└── cloud_config.py           # NEW - הגדרות cloud services
```

### 3.2 קבצים לעדכון

```
services/
├── ocr_service_new.py        # UPDATE - שימוש ב-Orchestrator
├── batch_processor.py        # UPDATE - שילוב שירותים חדשים
└── ocr_engine_manager.py     # UPDATE - Tesseract כ-fallback בלבד

config/
└── ocr_config.py             # UPDATE - הוספת הגדרות cloud

models/
└── recognition_result.py     # UPDATE - הוספת שדות חדשים

document/
└── requirements.txt          # UPDATE - הוספת תלויות
```

---

## 4. קוד מפורט לכל קובץ

### 4.1 config/cloud_config.py (חדש)

```python
"""
Cloud Services Configuration
הגדרות לשירותי ענן - Google Cloud Vision ו-Claude
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GoogleVisionConfig:
    """הגדרות Google Cloud Vision API"""
    
    # API Credentials
    # אפשרות 1: משתנה סביבה עם נתיב לקובץ JSON
    credentials_path: Optional[str] = field(
        default_factory=lambda: os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    )
    
    # אפשרות 2: API Key ישיר (פחות מומלץ)
    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get('GOOGLE_VISION_API_KEY')
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
    
    # API Key
    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get('ANTHROPIC_API_KEY')
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
```

### 4.2 services/google_vision_ocr.py (חדש)

```python
"""
Google Cloud Vision OCR Service
זיהוי טקסט עברי באמצעות Google Cloud Vision API
"""

import base64
import time
from typing import List, Optional, Tuple
import numpy as np
import cv2

from config.cloud_config import GoogleVisionConfig, get_cloud_config
from models.recognition_result import OcrResult


class GoogleVisionOcrService:
    """
    שירות OCR באמצעות Google Cloud Vision API
    מותאם לזיהוי טקסט עברי במשבצות תשבץ
    """
    
    def __init__(self, config: GoogleVisionConfig = None):
        """
        Args:
            config: הגדרות Google Vision (אם None, לוקח מ-cloud_config)
        """
        self.config = config or get_cloud_config().google
        self._client = None
        self._initialized = False
    
    def _initialize_client(self) -> None:
        """אתחול הלקוח של Google Cloud Vision"""
        if self._initialized:
            return
        
        try:
            from google.cloud import vision
            
            # בדיקת credentials
            if self.config.credentials_path:
                import os
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.config.credentials_path
                self._client = vision.ImageAnnotatorClient()
            elif self.config.api_key:
                # שימוש ב-API key (דרך REST)
                self._client = None  # נשתמש ב-REST API ישירות
                self._use_rest_api = True
            else:
                raise ValueError(
                    "Google Cloud Vision requires either:\n"
                    "1. GOOGLE_APPLICATION_CREDENTIALS environment variable, or\n"
                    "2. GOOGLE_VISION_API_KEY environment variable"
                )
            
            self._initialized = True
            print("✓ Google Cloud Vision client initialized")
            
        except ImportError:
            raise ImportError(
                "google-cloud-vision not installed. Run:\n"
                "pip install google-cloud-vision"
            )
    
    def recognize_text(self, image: np.ndarray) -> OcrResult:
        """
        זיהוי טקסט בתמונה בודדת
        
        Args:
            image: תמונת המשבצת (BGR numpy array)
            
        Returns:
            OcrResult עם הטקסט שזוהה
        """
        self._initialize_client()
        start_time = time.time()
        
        try:
            # המרה ל-bytes
            image_bytes = self._image_to_bytes(image)
            
            if hasattr(self, '_use_rest_api') and self._use_rest_api:
                result = self._recognize_with_rest_api(image_bytes)
            else:
                result = self._recognize_with_client(image_bytes)
            
            result.processing_time = time.time() - start_time
            return result
            
        except Exception as e:
            return OcrResult(
                text="",
                confidence=0.0,
                engine_used="google_vision",
                error=str(e),
                processing_time=time.time() - start_time
            )
    
    def _recognize_with_client(self, image_bytes: bytes) -> OcrResult:
        """זיהוי באמצעות Google Cloud Vision client library"""
        from google.cloud import vision
        
        image = vision.Image(content=image_bytes)
        
        # הגדרת שפות
        image_context = vision.ImageContext(
            language_hints=self.config.language_hints
        )
        
        # קריאה ל-API
        response = self._client.text_detection(
            image=image,
            image_context=image_context
        )
        
        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")
        
        # עיבוד תוצאות
        texts = response.text_annotations
        
        if not texts:
            return OcrResult(
                text="",
                confidence=0.0,
                engine_used="google_vision",
                raw_result=response
            )
        
        # הטקסט הראשון הוא הטקסט המלא
        full_text = texts[0].description.strip()
        
        # חישוב confidence - Google Vision לא מחזיר confidence ישירות
        # נשתמש ב-heuristic מבוסס על מספר התווים שזוהו
        confidence = self._estimate_confidence(texts, full_text)
        
        # חילוץ bboxes
        bboxes = []
        for text in texts[1:]:  # דלג על הראשון (full text)
            vertices = text.bounding_poly.vertices
            bbox = [[v.x, v.y] for v in vertices]
            bboxes.append(bbox)
        
        return OcrResult(
            text=full_text,
            confidence=confidence,
            engine_used="google_vision",
            bbox=bboxes,
            raw_result=response
        )
    
    def _recognize_with_rest_api(self, image_bytes: bytes) -> OcrResult:
        """זיהוי באמצעות REST API (כשמשתמשים ב-API key)"""
        import requests
        
        url = f"https://vision.googleapis.com/v1/images:annotate?key={self.config.api_key}"
        
        # בניית הבקשה
        request_body = {
            "requests": [{
                "image": {
                    "content": base64.b64encode(image_bytes).decode('utf-8')
                },
                "features": [{
                    "type": "TEXT_DETECTION",
                    "maxResults": self.config.max_results
                }],
                "imageContext": {
                    "languageHints": self.config.language_hints
                }
            }]
        }
        
        # שליחת הבקשה עם retries
        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(url, json=request_body, timeout=30)
                response.raise_for_status()
                result = response.json()
                break
            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise e
                time.sleep(self.config.retry_delay * (attempt + 1))
        
        # עיבוד התוצאות
        annotations = result.get('responses', [{}])[0].get('textAnnotations', [])
        
        if not annotations:
            return OcrResult(
                text="",
                confidence=0.0,
                engine_used="google_vision_rest",
                raw_result=result
            )
        
        full_text = annotations[0].get('description', '').strip()
        confidence = self._estimate_confidence(annotations, full_text)
        
        # חילוץ bboxes
        bboxes = []
        for ann in annotations[1:]:
            vertices = ann.get('boundingPoly', {}).get('vertices', [])
            bbox = [[v.get('x', 0), v.get('y', 0)] for v in vertices]
            bboxes.append(bbox)
        
        return OcrResult(
            text=full_text,
            confidence=confidence,
            engine_used="google_vision_rest",
            bbox=bboxes,
            raw_result=result
        )
    
    def _image_to_bytes(self, image: np.ndarray) -> bytes:
        """המרת תמונה ל-bytes"""
        # upscale לתמונות קטנות
        h, w = image.shape[:2]
        if h < 100 or w < 100:
            scale = max(100 / h, 100 / w, 2.0)
            image = cv2.resize(image, None, fx=scale, fy=scale, 
                             interpolation=cv2.INTER_CUBIC)
        
        # המרה ל-PNG bytes
        _, buffer = cv2.imencode('.png', image)
        return buffer.tobytes()
    
    def _estimate_confidence(self, annotations, full_text: str) -> float:
        """
        הערכת confidence - Google Vision לא מחזיר confidence ישירות
        משתמשים ב-heuristics
        """
        if not full_text:
            return 0.0
        
        # בדיקה שיש תווים עבריים
        hebrew_chars = set('אבגדהוזחטיכלמנסעפצקרשתךםןףץ')
        hebrew_count = sum(1 for c in full_text if c in hebrew_chars)
        total_chars = len(full_text.replace(' ', ''))
        
        if total_chars == 0:
            return 0.0
        
        hebrew_ratio = hebrew_count / total_chars
        
        # אם יש לפחות 50% עברית, confidence גבוה
        if hebrew_ratio > 0.5:
            return 0.85 + (hebrew_ratio - 0.5) * 0.3  # 0.85-1.0
        elif hebrew_ratio > 0.2:
            return 0.6 + hebrew_ratio * 0.5  # 0.6-0.85
        else:
            return 0.3 + hebrew_ratio * 1.5  # 0.3-0.6
    
    def batch_recognize(self, images: List[np.ndarray]) -> List[OcrResult]:
        """
        זיהוי batch של תמונות
        
        Args:
            images: רשימת תמונות
            
        Returns:
            רשימת תוצאות OCR
        """
        self._initialize_client()
        
        results = []
        
        # עיבוד ב-batches
        for i in range(0, len(images), self.config.batch_size):
            batch = images[i:i + self.config.batch_size]
            
            # לכל תמונה ב-batch
            for image in batch:
                result = self.recognize_text(image)
                results.append(result)
        
        return results
    
    def preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocessing מותאם ל-Google Vision
        Google Vision עושה preprocessing טוב בעצמו, אז נעשה מינימום
        
        Args:
            image: תמונה מקורית
            
        Returns:
            תמונה מעובדת
        """
        # upscale לתמונות קטנות
        h, w = image.shape[:2]
        if h < 50 or w < 50:
            scale = max(50 / h, 50 / w, 3.0)
            image = cv2.resize(image, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_CUBIC)
        
        # שיפור ניגודיות קל
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        l = clahe.apply(l)
        image = cv2.merge((l, a, b))
        image = cv2.cvtColor(image, cv2.COLOR_LAB2BGR)
        
        return image
```

### 4.3 services/claude_arrow_detector.py (חדש)

```python
"""
Claude Vision Arrow Detector
זיהוי כיוון חצים באמצעות Claude Vision API
"""

import base64
import time
import json
import re
from typing import Optional, Dict, List, Tuple
import numpy as np
import cv2

from config.cloud_config import ClaudeVisionConfig, get_cloud_config
from models.recognition_result import ArrowResult


class ClaudeArrowDetector:
    """
    זיהוי חצים באמצעות Claude Vision API
    יתרון: הבנת הקשר ויזואלי, זיהוי מדויק של כיוונים מורכבים
    """
    
    # מיפוי שמות חצים - תואם לשמות הקיימים ב-ArrowConfig
    ARROW_TYPES = {
        # Straight arrows
        "right": "straight-right",
        "left": "straight-left",
        "down": "straight-down",
        "up": "straight-up",
        "straight-right": "straight-right",
        "straight-left": "straight-left",
        "straight-down": "straight-down",
        "straight-up": "straight-up",
        
        # Step arrows - normalized names
        "up-right": "start-up-turn-right",
        "up-left": "start-up-turn-left",
        "down-right": "start-down-turn-right",
        "down-left": "start-down-turn-left",
        "left-down": "start-left-turn-down",
        "left-up": "start-left-turn-up",
        "right-down": "start-right-turn-down",
        "right-up": "start-right-turn-up",
        
        # Full names (for completeness)
        "start-up-turn-right": "start-up-turn-right",
        "start-up-turn-left": "start-up-turn-left",
        "start-down-turn-right": "start-down-turn-right",
        "start-down-turn-left": "start-down-turn-left",
        "start-left-turn-down": "start-left-turn-down",
        "start-left-turn-up": "start-left-turn-up",
        "start-right-turn-down": "start-right-turn-down",
        "start-right-turn-up": "start-right-turn-up",
        
        # No arrow
        "none": "none",
        "no_arrow": "none",
        "empty": "none",
    }
    
    DETECTION_PROMPT = """אתה מנתח תמונות של משבצות בתשבץ עברי.
המשימה שלך היא לזהות אם יש חץ במשבצת ומה הכיוון שלו.

סוגי חצים אפשריים:
1. חצים ישרים:
   - right: חץ ימינה →
   - left: חץ שמאלה ←
   - down: חץ למטה ↓
   - up: חץ למעלה ↑

2. חצים מדורגים (step arrows) - חץ שמתחיל בכיוון אחד ואז פונה:
   - up-right: מתחיל למעלה ופונה ימינה ↑→
   - up-left: מתחיל למעלה ופונה שמאלה ↑←
   - down-right: מתחיל למטה ופונה ימינה ↓→
   - down-left: מתחיל למטה ופונה שמאלה ↓←
   - left-down: מתחיל שמאלה ופונה למטה ←↓
   - left-up: מתחיל שמאלה ופונה למעלה ←↑
   - right-down: מתחיל ימינה ופונה למטה →↓
   - right-up: מתחיל ימינה ופונה למעלה →↑

3. none: אין חץ במשבצת

ענה בפורמט JSON בלבד:
{
    "has_arrow": true/false,
    "direction": "שם הכיוון מהרשימה למעלה",
    "confidence": 0.0-1.0,
    "description": "תיאור קצר של מה שזיהית"
}

אם אין חץ, החזר:
{
    "has_arrow": false,
    "direction": "none",
    "confidence": 1.0,
    "description": "לא זוהה חץ במשבצת"
}
"""
    
    def __init__(self, config: ClaudeVisionConfig = None):
        """
        Args:
            config: הגדרות Claude Vision (אם None, לוקח מ-cloud_config)
        """
        self.config = config or get_cloud_config().claude
        self._client = None
        self._initialized = False
    
    def _initialize_client(self) -> None:
        """אתחול הלקוח של Anthropic"""
        if self._initialized:
            return
        
        try:
            import anthropic
            
            if not self.config.api_key:
                raise ValueError(
                    "Claude Vision requires ANTHROPIC_API_KEY environment variable"
                )
            
            self._client = anthropic.Anthropic(api_key=self.config.api_key)
            self._initialized = True
            print("✓ Claude Vision client initialized")
            
        except ImportError:
            raise ImportError(
                "anthropic not installed. Run:\n"
                "pip install anthropic"
            )
    
    def detect_arrow(
        self,
        cell_image: np.ndarray,
        cell_bbox: Tuple[int, int, int, int] = None
    ) -> ArrowResult:
        """
        זיהוי חץ במשבצת
        
        Args:
            cell_image: תמונת המשבצת (BGR numpy array)
            cell_bbox: קואורדינטות המשבצת (לא בשימוש כרגע)
            
        Returns:
            ArrowResult עם כיוון החץ שזוהה
        """
        self._initialize_client()
        start_time = time.time()
        
        try:
            # המרה ל-base64
            image_base64 = self._image_to_base64(cell_image)
            
            # קריאה ל-API
            response = self._call_claude_api(image_base64)
            
            # פענוח התשובה
            result = self._parse_response(response)
            result.processing_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            return ArrowResult(
                direction="none",
                confidence=0.0,
                processing_time=time.time() - start_time,
                template_matched=f"error: {str(e)}"
            )
    
    def _call_claude_api(self, image_base64: str) -> str:
        """קריאה ל-Claude Vision API"""
        for attempt in range(self.config.max_retries):
            try:
                message = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": image_base64
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": self.DETECTION_PROMPT
                                }
                            ]
                        }
                    ]
                )
                
                return message.content[0].text
                
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise e
                time.sleep(self.config.retry_delay * (attempt + 1))
    
    def _parse_response(self, response_text: str) -> ArrowResult:
        """פענוח תשובת Claude"""
        try:
            # חיפוש JSON בתשובה
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # ניסיון לפרסר את כל התשובה כ-JSON
                data = json.loads(response_text)
            
            # נורמליזציה של שם הכיוון
            raw_direction = data.get('direction', 'none').lower().strip()
            direction = self.ARROW_TYPES.get(raw_direction, raw_direction)
            
            # אם הכיוון לא מוכר, החזר none
            if direction not in self.ARROW_TYPES.values():
                direction = 'none'
            
            confidence = float(data.get('confidence', 0.5))
            
            return ArrowResult(
                direction=direction,
                confidence=confidence,
                match_location=(0, 0),
                scale_used=1.0,
                template_matched=f"claude: {data.get('description', '')}"
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # אם לא הצלחנו לפרסר, ננסה להבין מהטקסט
            return self._parse_text_response(response_text)
    
    def _parse_text_response(self, text: str) -> ArrowResult:
        """ניסיון לפענח תשובה לא-JSON"""
        text_lower = text.lower()
        
        # חיפוש מילות מפתח
        for keyword, direction in self.ARROW_TYPES.items():
            if keyword in text_lower:
                return ArrowResult(
                    direction=direction,
                    confidence=0.6,  # confidence נמוך יותר כי לא היה JSON
                    template_matched=f"claude_text_parse: {text[:100]}"
                )
        
        return ArrowResult(
            direction="none",
            confidence=0.3,
            template_matched=f"claude_parse_failed: {text[:100]}"
        )
    
    def _image_to_base64(self, image: np.ndarray) -> str:
        """המרת תמונה ל-base64"""
        # upscale לתמונות קטנות - Claude עובד טוב יותר עם תמונות גדולות יותר
        h, w = image.shape[:2]
        if h < 100 or w < 100:
            scale = max(100 / h, 100 / w, 2.0)
            image = cv2.resize(image, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_CUBIC)
        
        # המרה ל-PNG ואז ל-base64
        _, buffer = cv2.imencode('.png', image)
        return base64.b64encode(buffer).decode('utf-8')
    
    def batch_detect(self, images: List[np.ndarray]) -> List[ArrowResult]:
        """
        זיהוי batch של תמונות
        
        Args:
            images: רשימת תמונות
            
        Returns:
            רשימת תוצאות ArrowResult
        """
        results = []
        for image in images:
            result = self.detect_arrow(image)
            results.append(result)
        return results
    
    def get_arrow_icon(self, arrow_direction: str) -> str:
        """
        המרת כיוון חץ לאייקון (לתצוגה ב-UI)
        
        Args:
            arrow_direction: שם הכיוון
            
        Returns:
            emoji string
        """
        mapping = {
            "straight-left": "⬅️",
            "straight-right": "➡️",
            "straight-down": "⬇️",
            "straight-up": "⬆️",
            "start-up-turn-right": "↗️",
            "start-up-turn-left": "↖️",
            "start-down-turn-right": "↘️",
            "start-down-turn-left": "↙️",
            "start-left-turn-down": "↙️",
            "start-left-turn-up": "↖️",
            "start-right-turn-down": "↘️",
            "start-right-turn-up": "↗️",
            "none": "❓"
        }
        return mapping.get(arrow_direction, "❓")
```

### 4.4 services/recognition_orchestrator.py (חדש)

```python
"""
Recognition Orchestrator
תיאום בין שירותי הזיהוי השונים עם fallback אוטומטי
"""

import time
from typing import Optional, Tuple
from dataclasses import dataclass
import numpy as np

from config.cloud_config import CloudServicesConfig, get_cloud_config
from models.recognition_result import OcrResult, ArrowResult, CellRecognitionResult


@dataclass
class RecognitionConfig:
    """הגדרות לזיהוי"""
    use_google_for_text: bool = True
    use_claude_for_arrows: bool = True
    use_fallback: bool = True
    fallback_confidence_threshold: float = 0.5


class RecognitionOrchestrator:
    """
    מתאם בין שירותי הזיהוי השונים
    - Google Cloud Vision לטקסט עברי
    - Claude Vision לחצים
    - Tesseract + Template Matching כ-fallback
    """
    
    def __init__(self, config: CloudServicesConfig = None):
        """
        Args:
            config: הגדרות cloud services
        """
        self.config = config or get_cloud_config()
        
        # Lazy initialization - יטען רק כשצריך
        self._google_ocr = None
        self._claude_arrow = None
        self._tesseract_ocr = None
        self._template_arrow = None
    
    @property
    def google_ocr(self):
        """Lazy load Google Vision OCR"""
        if self._google_ocr is None:
            from services.google_vision_ocr import GoogleVisionOcrService
            self._google_ocr = GoogleVisionOcrService(self.config.google)
        return self._google_ocr
    
    @property
    def claude_arrow(self):
        """Lazy load Claude Arrow Detector"""
        if self._claude_arrow is None:
            from services.claude_arrow_detector import ClaudeArrowDetector
            self._claude_arrow = ClaudeArrowDetector(self.config.claude)
        return self._claude_arrow
    
    @property
    def tesseract_ocr(self):
        """Lazy load Tesseract OCR (fallback)"""
        if self._tesseract_ocr is None:
            from services.ocr_engine_manager import OcrEngineManager
            self._tesseract_ocr = OcrEngineManager()
            self._tesseract_ocr.initialize_engines()
        return self._tesseract_ocr
    
    @property
    def template_arrow(self):
        """Lazy load Template Arrow Detector (fallback)"""
        if self._template_arrow is None:
            from services.arrow_detector import ArrowDetector
            self._template_arrow = ArrowDetector()
        return self._template_arrow
    
    def recognize_cell(
        self,
        cell_image: np.ndarray,
        cell_bbox: Tuple[int, int, int, int] = None
    ) -> Tuple[OcrResult, ArrowResult]:
        """
        זיהוי תוכן משבצת - טקסט + חץ
        
        Args:
            cell_image: תמונת המשבצת (BGR)
            cell_bbox: קואורדינטות המשבצת
            
        Returns:
            Tuple של (OcrResult, ArrowResult)
        """
        # זיהוי טקסט
        ocr_result = self._recognize_text(cell_image)
        
        # זיהוי חץ
        arrow_result = self._detect_arrow(cell_image, cell_bbox)
        
        return ocr_result, arrow_result
    
    def _recognize_text(self, image: np.ndarray) -> OcrResult:
        """זיהוי טקסט עם fallback"""
        
        # ניסיון עם Google Vision
        if self.config.text_ocr_provider == "google":
            try:
                result = self.google_ocr.recognize_text(image)
                
                # בדיקה אם צריך fallback
                if (self.config.enable_fallback and 
                    self.config.fallback_on_low_confidence and
                    result.confidence < self.config.fallback_confidence_threshold):
                    
                    print(f"  Google Vision low confidence ({result.confidence:.2f}), trying Tesseract...")
                    fallback_result = self._recognize_text_tesseract(image)
                    
                    # בחירת התוצאה הטובה יותר
                    if fallback_result.confidence > result.confidence:
                        fallback_result.fallback_triggered = True
                        return fallback_result
                
                return result
                
            except Exception as e:
                print(f"  Google Vision error: {e}")
                if self.config.enable_fallback and self.config.fallback_on_error:
                    print("  Falling back to Tesseract...")
                    result = self._recognize_text_tesseract(image)
                    result.fallback_triggered = True
                    return result
                raise
        
        # Tesseract כ-primary
        return self._recognize_text_tesseract(image)
    
    def _recognize_text_tesseract(self, image: np.ndarray) -> OcrResult:
        """זיהוי טקסט עם Tesseract"""
        preprocessed = self.tesseract_ocr.preprocess_image(image)
        return self.tesseract_ocr.recognize_text(preprocessed)
    
    def _detect_arrow(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int] = None
    ) -> ArrowResult:
        """זיהוי חץ עם fallback"""
        
        # ניסיון עם Claude Vision
        if self.config.arrow_detector_provider == "claude":
            try:
                result = self.claude_arrow.detect_arrow(image, bbox)
                
                # בדיקה אם צריך fallback
                if (self.config.enable_fallback and
                    self.config.fallback_on_low_confidence and
                    result.confidence < self.config.fallback_confidence_threshold):
                    
                    print(f"  Claude Arrow low confidence ({result.confidence:.2f}), trying Template Matching...")
                    fallback_result = self.template_arrow.detect_arrow(image, bbox)
                    
                    if fallback_result.confidence > result.confidence:
                        return fallback_result
                
                return result
                
            except Exception as e:
                print(f"  Claude Arrow error: {e}")
                if self.config.enable_fallback and self.config.fallback_on_error:
                    print("  Falling back to Template Matching...")
                    return self.template_arrow.detect_arrow(image, bbox)
                raise
        
        # Template Matching כ-primary
        return self.template_arrow.detect_arrow(image, bbox)
    
    def is_google_available(self) -> bool:
        """בדיקה אם Google Vision זמין"""
        try:
            return bool(self.config.google.credentials_path or 
                       self.config.google.api_key)
        except:
            return False
    
    def is_claude_available(self) -> bool:
        """בדיקה אם Claude Vision זמין"""
        try:
            return bool(self.config.claude.api_key)
        except:
            return False
    
    def get_active_providers(self) -> dict:
        """החזרת הספקים הפעילים"""
        return {
            "text_ocr": self.config.text_ocr_provider,
            "arrow_detector": self.config.arrow_detector_provider,
            "google_available": self.is_google_available(),
            "claude_available": self.is_claude_available(),
            "fallback_enabled": self.config.enable_fallback
        }
```

### 4.5 עדכון services/batch_processor.py

שינויים נדרשים בקובץ הקיים:

```python
"""
Batch Processor - Updated for Phase 2
עיבוד מקבילי של משבצות גריד עם תמיכה ב-Cloud Services
"""

import time
import numpy as np
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

from models.grid import GridMatrix, Cell, CellType
from models.recognition_result import CellRecognitionResult
from services.recognition_orchestrator import RecognitionOrchestrator
from services.confidence_scorer import ConfidenceScorer


class BatchProcessor:
    """
    עיבוד מקבילי של משבצות גריד
    Phase 2: משתמש ב-RecognitionOrchestrator לתיאום בין השירותים
    """

    def __init__(
        self,
        orchestrator: RecognitionOrchestrator = None,
        confidence_scorer: ConfidenceScorer = None,
        max_workers: int = None
    ):
        """
        Args:
            orchestrator: מתאם הזיהוי (אם None, יוצר אחד חדש)
            confidence_scorer: מחשב ביטחון (אם None, יוצר אחד חדש)
            max_workers: מספר threads (None = cpu_count)
        """
        self.orchestrator = orchestrator or RecognitionOrchestrator()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        
        # מספר workers מותאם - פחות ב-cloud כי יש rate limits
        if max_workers is None:
            providers = self.orchestrator.get_active_providers()
            if providers.get('google_available') or providers.get('claude_available'):
                self.max_workers = min(4, cpu_count())  # הגבלה ל-4 לcloud
            else:
                self.max_workers = cpu_count()
        else:
            self.max_workers = max_workers

    def process_grid(
        self,
        original_image: np.ndarray,
        grid: GridMatrix,
        progress_callback: Callable[[float], None] = None
    ) -> GridMatrix:
        """
        עיבוד כל משבצות הגריד
        
        Args:
            original_image: התמונה המקורית (BGR)
            grid: אובייקט הגריד עם bbox לכל משבצת
            progress_callback: פונקציה לעדכון התקדמות
            
        Returns:
            GridMatrix מעודכן עם תוצאות הזיהוי
        """
        start_time = time.time()
        
        # הצגת ספקים פעילים
        providers = self.orchestrator.get_active_providers()
        print(f"Active providers: OCR={providers['text_ocr']}, Arrows={providers['arrow_detector']}")

        # הכנת tasks
        tasks = self._prepare_tasks(original_image, grid)

        if not tasks:
            print("No CLUE cells to process")
            return grid

        print(f"Processing {len(tasks)} cells with {self.max_workers} workers...")

        # עיבוד מקבילי
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._process_single_cell, task): task
                for task in tasks
            }

            completed = 0
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                cell_key = (task['row'], task['col'])

                try:
                    result = future.result()
                    results[cell_key] = result
                except Exception as e:
                    print(f"Error processing cell ({task['row']}, {task['col']}): {e}")
                    results[cell_key] = CellRecognitionResult(error=str(e))

                completed += 1
                if progress_callback:
                    progress_callback(completed / len(tasks))

        # עדכון הגריד
        self._update_grid_with_results(grid, results)

        total_time = time.time() - start_time
        print(f"✓ Batch processing completed in {total_time:.2f}s")
        print(f"  Average time per cell: {total_time / len(tasks):.3f}s")

        return grid

    def _prepare_tasks(self, original_image: np.ndarray, grid: GridMatrix) -> list:
        """הכנת רשימת tasks לעיבוד"""
        tasks = []

        for r in range(grid.rows):
            for c in range(grid.cols):
                cell = grid.matrix[r][c]

                if cell.type == CellType.CLUE and hasattr(cell, 'bbox'):
                    x1, y1, x2, y2 = cell.bbox
                    cell_image = original_image[y1:y2, x1:x2].copy()

                    if cell_image.size > 0:
                        tasks.append({
                            'row': r,
                            'col': c,
                            'image': cell_image,
                            'bbox': cell.bbox,
                            'cell': cell
                        })

        return tasks

    def _process_single_cell(self, task: dict) -> CellRecognitionResult:
        """עיבוד משבצת בודדת"""
        start_time = time.time()
        cell_image = task['image']
        cell_bbox = task['bbox']
        row, col = task['row'], task['col']

        try:
            # Phase 2: שימוש ב-Orchestrator
            print(f"  [{row},{col}] Processing with orchestrator...")
            ocr_result, arrow_result = self.orchestrator.recognize_cell(
                cell_image, 
                cell_bbox
            )
            print(f"  [{row},{col}] OCR: '{ocr_result.text[:20] if ocr_result.text else ''}' ({ocr_result.confidence:.2f})")
            print(f"  [{row},{col}] Arrow: {arrow_result.direction} ({arrow_result.confidence:.2f})")

            # Confidence Scoring
            confidence_score = self.confidence_scorer.calculate_confidence(
                ocr_result,
                arrow_result,
                cell_image
            )

            processing_time = time.time() - start_time

            return CellRecognitionResult(
                ocr_result=ocr_result,
                arrow_result=arrow_result,
                confidence=confidence_score,
                processing_time=processing_time,
                cell_image=cell_image
            )

        except Exception as e:
            import traceback
            print(f"  [{row},{col}] ERROR: {e}")
            traceback.print_exc()
            return CellRecognitionResult(
                error=str(e),
                processing_time=time.time() - start_time
            )

    def _update_grid_with_results(self, grid: GridMatrix, results: dict) -> None:
        """עדכון הגריד עם התוצאות"""
        # ... (שאר הקוד נשאר זהה)
        print(f"Updating grid with {len(results)} results...")
        updated_count = 0

        for (row, col), result in results.items():
            cell = grid.matrix[row][col]
            cell.recognition_result = result

            ocr_text = result.ocr_result.text if result.ocr_result else ""
            ocr_conf = result.ocr_result.confidence if result.ocr_result else 0.0
            arrow_dir = result.arrow_result.direction if result.arrow_result else 'none'
            arrow_conf = result.arrow_result.confidence if result.arrow_result else 0.0
            overall_conf = result.confidence.overall if result.confidence else 0.0

            clue_dict = {
                'text': ocr_text,
                'path': arrow_dir,
                'zone': 'full_cell',
                'confidence': overall_conf,
                'ocr_confidence': ocr_conf,
                'arrow_confidence': arrow_conf
            }

            if not hasattr(cell, 'parsed_clues') or cell.parsed_clues is None:
                cell.parsed_clues = []
            cell.parsed_clues.append(clue_dict)
            updated_count += 1

            if updated_count <= 3:
                print(f"  Cell ({row},{col}): text='{ocr_text[:20]}...' conf={overall_conf:.2f}")

            if result.cell_image is not None:
                import cv2
                import base64
                _, buffer = cv2.imencode('.png', result.cell_image)
                b64_img = base64.b64encode(buffer).decode('utf-8')
                cell.debug_image = f"data:image/png;base64,{b64_img}"

        print(f"✓ Updated {updated_count} cells with parsed_clues")

    def get_processing_stats(self, grid: GridMatrix) -> dict:
        """חישוב סטטיסטיקות על העיבוד"""
        # ... (שאר הקוד נשאר זהה)
        total_cells = 0
        high_confidence = 0
        medium_confidence = 0
        low_confidence = 0
        total_time = 0.0
        ocr_confidences = []
        arrow_confidences = []

        for r in range(grid.rows):
            for c in range(grid.cols):
                cell = grid.matrix[r][c]

                if hasattr(cell, 'recognition_result') and cell.recognition_result:
                    result = cell.recognition_result
                    total_cells += 1

                    if result.confidence:
                        if result.confidence.level.value == 'HIGH':
                            high_confidence += 1
                        elif result.confidence.level.value == 'MEDIUM':
                            medium_confidence += 1
                        else:
                            low_confidence += 1

                    if result.processing_time:
                        total_time += result.processing_time

                    if result.ocr_result:
                        ocr_confidences.append(result.ocr_result.confidence)

                    if result.arrow_result:
                        arrow_confidences.append(result.arrow_result.confidence)

        return {
            'total_cells': total_cells,
            'high_confidence': high_confidence,
            'medium_confidence': medium_confidence,
            'low_confidence': low_confidence,
            'high_confidence_pct': (high_confidence / total_cells * 100) if total_cells else 0,
            'total_time': total_time,
            'avg_time_per_cell': (total_time / total_cells) if total_cells else 0,
            'avg_ocr_confidence': (sum(ocr_confidences) / len(ocr_confidences)) if ocr_confidences else 0,
            'avg_arrow_confidence': (sum(arrow_confidences) / len(arrow_confidences)) if arrow_confidences else 0
        }
```

### 4.6 עדכון services/ocr_service_new.py

```python
"""
OCR Service (Phase 2 - Cloud Integration)
שירות OCR עם תמיכה ב-Google Cloud Vision ו-Claude
"""

import cv2
import numpy as np
import streamlit as st
from models.grid import GridMatrix
from services.recognition_orchestrator import RecognitionOrchestrator
from services.confidence_scorer import ConfidenceScorer
from services.batch_processor import BatchProcessor
from config.cloud_config import get_cloud_config, CloudServicesConfig


class OcrService:
    """
    שירות OCR - Phase 2
    משתמש ב-Google Cloud Vision לטקסט + Claude לחצים
    """

    def __init__(
        self,
        use_cloud_services: bool = True,
        config: CloudServicesConfig = None
    ):
        """
        Args:
            use_cloud_services: אם True, משתמש ב-cloud APIs
                               אם False, משתמש ב-local fallback בלבד
            config: הגדרות cloud services (אופציונלי)
        """
        self.use_cloud_services = use_cloud_services
        self.config = config or get_cloud_config()

        # שינוי ההגדרות אם לא רוצים cloud
        if not use_cloud_services:
            self.config.text_ocr_provider = "tesseract"
            self.config.arrow_detector_provider = "template"

        print(f"Initializing OCR Service (Phase 2)...")
        print(f"  Text OCR: {self.config.text_ocr_provider}")
        print(f"  Arrow Detection: {self.config.arrow_detector_provider}")

        # יצירת components
        self.orchestrator = RecognitionOrchestrator(self.config)
        self.confidence_scorer = ConfidenceScorer()
        self.batch_processor = BatchProcessor(
            self.orchestrator,
            self.confidence_scorer
        )

        print("✓ OCR Service ready")

    def recognize_clues(
        self,
        original_image: np.ndarray,
        grid: GridMatrix
    ) -> GridMatrix:
        """
        זיהוי הגדרות במשבצות

        Args:
            original_image: התמונה המקורית
            grid: אובייקט הגריד

        Returns:
            GridMatrix מעודכן עם תוצאות הזיהוי
        """
        return self._recognize_with_orchestrator(original_image, grid)

    def _recognize_with_orchestrator(
        self,
        original_image: np.ndarray,
        grid: GridMatrix
    ) -> GridMatrix:
        """זיהוי עם Orchestrator"""
        from models.grid import CellType

        # דיבוג
        total_cells = grid.rows * grid.cols
        clue_cells = sum(1 for r in range(grid.rows) for c in range(grid.cols)
                        if grid.matrix[r][c].type == CellType.CLUE)
        bbox_cells = sum(1 for r in range(grid.rows) for c in range(grid.cols)
                        if hasattr(grid.matrix[r][c], 'bbox'))

        print(f"Grid info: {grid.rows}x{grid.cols} = {total_cells} cells")
        print(f"  CLUE cells: {clue_cells}")
        print(f"  Cells with bbox: {bbox_cells}")

        # הצגת ספקים פעילים
        providers = self.orchestrator.get_active_providers()
        st.info(f"""
        **הגדרות זיהוי:**
        - זיהוי טקסט: {providers['text_ocr']} {'✅' if providers['google_available'] else '⚠️ לא מוגדר'}
        - זיהוי חצים: {providers['arrow_detector']} {'✅' if providers['claude_available'] else '⚠️ לא מוגדר'}
        - Fallback: {'מופעל' if providers['fallback_enabled'] else 'מושבת'}
        """)

        st.write(f"**גריד:** {grid.rows}x{grid.cols}, משבצות הגדרה: {clue_cells}")

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("מאתחל עיבוד...")

        def update_progress(pct):
            progress_bar.progress(pct)
            status_text.text(f"מעבד: {int(pct * 100)}%")

        # עיבוד הגריד
        updated_grid = self.batch_processor.process_grid(
            original_image,
            grid,
            progress_callback=update_progress
        )

        # סטטיסטיקות
        stats = self.batch_processor.get_processing_stats(updated_grid)

        status_text.empty()
        progress_bar.empty()

        # הצגת metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "זמן עיבוד",
                f"{stats['total_time']:.1f}s",
                f"{stats['avg_time_per_cell']:.2f}s/cell"
            )
        with col2:
            st.metric(
                "ביטחון גבוה",
                f"{stats['high_confidence_pct']:.0f}%",
                f"{stats['high_confidence']}/{stats['total_cells']}"
            )
        with col3:
            st.metric(
                "דיוק OCR ממוצע",
                f"{stats['avg_ocr_confidence']:.2f}"
            )
        with col4:
            st.metric(
                "דיוק חצים ממוצע",
                f"{stats['avg_arrow_confidence']:.2f}"
            )

        return updated_grid
```

### 4.7 עדכון document/requirements.txt

```
streamlit>=1.28.0
opencv-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
streamlit-drawable-canvas-fix>=0.9.8

# Phase 1: OCR engines (fallback)
pytesseract>=0.3.10

# Phase 2: Cloud Services
google-cloud-vision>=3.4.0
anthropic>=0.18.0

# Optional: EasyOCR/PaddleOCR (disabled by default)
# easyocr>=1.7.0
# paddleocr>=2.7.0

# Utilities
requests>=2.31.0
pydantic>=2.0.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
```

---

## 5. הוראות התקנה והגדרה

### 5.1 התקנת dependencies

```bash
# התקנה בסיסית
pip install google-cloud-vision anthropic

# או מ-requirements.txt
pip install -r document/requirements.txt
```

### 5.2 הגדרת API Keys

#### Google Cloud Vision

**אפשרות 1: Service Account (מומלץ)**
1. צור Service Account ב-Google Cloud Console
2. הורד את קובץ ה-JSON
3. הגדר משתנה סביבה:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

**אפשרות 2: API Key**
1. צור API Key ב-Google Cloud Console
2. הגדר משתנה סביבה:
```bash
export GOOGLE_VISION_API_KEY="your-api-key"
```

#### Claude Vision (Anthropic)

1. קבל API Key מ-https://console.anthropic.com/
2. הגדר משתנה סביבה:
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### 5.3 קובץ .env לפיתוח מקומי

צור קובץ `.env` בתיקייה הראשית:

```env
# Google Cloud Vision
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
# או
GOOGLE_VISION_API_KEY=your-google-api-key

# Claude/Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key
```

---

## 6. שינויים ב-app.py

עדכן את ה-import ואת יצירת ה-OcrService:

```python
# שינוי ב-imports (שורה 7)
from services.ocr_service_new import OcrService

# שינוי באזור שלב 3 (שורות 208-216)
st.divider()
st.subheader("שלב 3: זיהוי ואימות ויזואלי")

# Phase 2: בחירת ספק
provider_option = st.radio(
    "בחר שיטת זיהוי:",
    ["☁️ Cloud (Google + Claude) - מומלץ", "💻 Local (Tesseract + Templates)"],
    horizontal=True
)
use_cloud = provider_option.startswith("☁️")

if st.button("🧠 הפעל זיהוי + הצג חיתוכים", type="primary"):
    ocr_service = OcrService(use_cloud_services=use_cloud)
    image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    updated_grid = ocr_service.recognize_clues(
        image_bgr,
        st.session_state.analyzed_grid
    )
    st.session_state.analyzed_grid = updated_grid
    st.success("✅ הזיהוי הושלם!")
```

---

## 7. מבנה קבצים סופי

```
crossword-solver/
├── app.py                          # UPDATED
├── config/
│   ├── __init__.py
│   ├── arrow_config.py
│   ├── confidence_config.py
│   ├── ocr_config.py
│   └── cloud_config.py             # NEW
├── services/
│   ├── __init__.py
│   ├── google_vision_ocr.py        # NEW
│   ├── claude_arrow_detector.py    # NEW
│   ├── recognition_orchestrator.py # NEW
│   ├── batch_processor.py          # UPDATED
│   ├── ocr_service_new.py          # UPDATED
│   ├── ocr_engine_manager.py       # Unchanged (fallback)
│   ├── arrow_detector.py           # Unchanged (fallback)
│   ├── confidence_scorer.py        # Unchanged
│   └── vision_service.py           # Unchanged
├── models/
│   ├── __init__.py
│   ├── grid.py
│   └── recognition_result.py       # Unchanged
├── document/
│   ├── requirements.txt            # UPDATED
│   └── ...
└── .env                            # NEW (לא ב-git)
```

---

## 8. בדיקות

### 8.1 בדיקת חיבור APIs

```python
# tests/test_cloud_services.py
import pytest
from services.google_vision_ocr import GoogleVisionOcrService
from services.claude_arrow_detector import ClaudeArrowDetector
import numpy as np
import cv2

def test_google_vision_connection():
    """בדיקה שGoogle Vision מחובר"""
    service = GoogleVisionOcrService()
    # יצירת תמונה פשוטה
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    cv2.putText(img, "test", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
    result = service.recognize_text(img)
    assert result is not None
    assert result.engine_used in ["google_vision", "google_vision_rest"]

def test_claude_vision_connection():
    """בדיקה ש-Claude Vision מחובר"""
    detector = ClaudeArrowDetector()
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    result = detector.detect_arrow(img)
    assert result is not None
    assert result.direction is not None
```

### 8.2 הרצת בדיקות

```bash
pytest tests/test_cloud_services.py -v
```

---

## 9. סיכום השינויים

| קובץ | פעולה | תיאור |
|------|-------|-------|
| `config/cloud_config.py` | חדש | הגדרות cloud services |
| `services/google_vision_ocr.py` | חדש | Google Cloud Vision OCR |
| `services/claude_arrow_detector.py` | חדש | Claude Vision לחצים |
| `services/recognition_orchestrator.py` | חדש | תיאום בין השירותים |
| `services/batch_processor.py` | עדכון | שימוש ב-Orchestrator |
| `services/ocr_service_new.py` | עדכון | ממשק cloud services |
| `app.py` | עדכון | UI לבחירת ספק |
| `document/requirements.txt` | עדכון | תלויות חדשות |

---

## 10. הערות ליישום

1. **סדר יצירת קבצים:**
   - קודם `config/cloud_config.py`
   - אח"כ `services/google_vision_ocr.py`
   - אח"כ `services/claude_arrow_detector.py`
   - אח"כ `services/recognition_orchestrator.py`
   - לבסוף עדכון `batch_processor.py` ו-`ocr_service_new.py`

2. **בדיקה אחרי כל שלב:**
   - וודא שה-imports עובדים
   - וודא שאין שגיאות syntax

3. **API Keys:**
   - אל תשכח להגדיר את משתני הסביבה!
   - ללא API keys המערכת תעבור אוטומטית ל-fallback

4. **Fallback:**
   - המערכת תמשיך לעבוד גם ללא cloud services
   - Tesseract + Template Matching ישמשו כגיבוי

---

*מסמך זה מכיל את כל המידע הנדרש לביצוע האינטגרציה. Claude Code צריך לבצע את השינויים לפי הסדר המתואר.*
