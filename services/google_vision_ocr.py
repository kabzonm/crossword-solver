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
        self._use_rest_api = False

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
            print("[OK] Google Cloud Vision client initialized")

        except ImportError:
            # אם אין את הספרייה, ננסה REST API
            if self.config.api_key:
                self._use_rest_api = True
                self._initialized = True
                print("[OK] Google Cloud Vision initialized (REST API mode)")
            else:
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

            if self._use_rest_api:
                result = self._recognize_with_rest_api(image_bytes)
            else:
                result = self._recognize_with_client(image_bytes)

            result.processing_time = time.time() - start_time
            return result

        except Exception as e:
            print(f"  Google Vision error: {e}")
            return OcrResult(
                text="",
                confidence=0.0,
                engine_used="google_vision",
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
