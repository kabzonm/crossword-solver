"""
Recognition Orchestrator
תיאום בין שירותי הזיהוי השונים עם fallback אוטומטי
"""

import time
from typing import Optional, Tuple, List
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
        cell_bbox: Tuple[int, int, int, int] = None,
        arrow_image: np.ndarray = None
    ) -> Tuple[OcrResult, List[ArrowResult]]:
        """
        זיהוי תוכן משבצת - טקסט + חצים

        Args:
            cell_image: תמונת המשבצת המדויקת (BGR) - לזיהוי טקסט
            cell_bbox: קואורדינטות המשבצת
            arrow_image: תמונה מורחבת עם שוליים (BGR) - לזיהוי חצים עם Claude

        Returns:
            Tuple של (OcrResult, List[ArrowResult]) - רשימה של עד 2 חצים
        """
        # זיהוי טקסט - משתמש בתמונת המשבצת המדויקת (בלי שוליים)
        ocr_result = self._recognize_text(cell_image)

        # זיהוי חצים - משתמש בתמונה המורחבת עם שוליים (כדי לראות את החצים)
        arrow_detection_image = arrow_image if arrow_image is not None else cell_image
        arrow_results = self._detect_arrows(arrow_detection_image, cell_bbox)

        return ocr_result, arrow_results

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

    def _detect_arrows(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int] = None
    ) -> List[ArrowResult]:
        """זיהוי חצים עם fallback - מחזיר רשימה של עד 2 חצים"""

        # ניסיון עם Claude Vision
        if self.config.arrow_detector_provider == "claude":
            try:
                results = self.claude_arrow.detect_arrow(image, bbox)

                # בדיקה אם צריך fallback (אם אין תוצאות או confidence נמוך)
                if (self.config.enable_fallback and
                    self.config.fallback_on_low_confidence and
                    (not results or all(r.confidence < self.config.fallback_confidence_threshold for r in results))):

                    print(f"  Claude Arrow low confidence, trying Template Matching...")
                    fallback_result = self.template_arrow.detect_arrow(image, bbox)

                    # Template matching מחזיר תוצאה בודדת, נחזיר כרשימה
                    if isinstance(fallback_result, list):
                        return fallback_result
                    return [fallback_result]

                return results

            except Exception as e:
                print(f"  Claude Arrow error: {e}")
                if self.config.enable_fallback and self.config.fallback_on_error:
                    print("  Falling back to Template Matching...")
                    fallback_result = self.template_arrow.detect_arrow(image, bbox)
                    if isinstance(fallback_result, list):
                        return fallback_result
                    return [fallback_result]
                raise

        # Template Matching כ-primary - מחזיר תוצאה בודדת, נעטוף ברשימה
        result = self.template_arrow.detect_arrow(image, bbox)
        if isinstance(result, list):
            return result
        return [result]

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
