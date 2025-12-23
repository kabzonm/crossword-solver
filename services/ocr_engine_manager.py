"""
OCR Engine Manager
מנהל מנועי OCR עם fallback אוטומטי
"""

import time
import numpy as np
from typing import List, Optional
import cv2
import os

from config.ocr_config import OcrConfig
from models.recognition_result import OcrResult


class OcrEngineManager:
    """
    מנהל מנועי OCR עם fallback אוטומטי
    תומך ב-Tesseract (primary לעברית), EasyOCR, ו-PaddleOCR
    """

    def __init__(self, config: OcrConfig = None):
        """
        Args:
            config: הגדרות OCR (אם None, משתמש בברירת מחדל)
        """
        self.config = config or OcrConfig()
        self.primary_engine = None
        self.fallback_engine = None
        self._primary_loaded = False
        self._fallback_loaded = False

    def initialize_engines(self) -> None:
        """
        טעינה עצלה של מנועי OCR
        טוען את המנוע הראשי מיד, והמנוע הגיבוי רק בעת הצורך
        """
        if not self._primary_loaded:
            print(f"Loading {self.config.PRIMARY_ENGINE}...")
            if self.config.PRIMARY_ENGINE == 'tesseract':
                self._load_tesseract()
            elif self.config.PRIMARY_ENGINE == 'easyocr':
                self._load_easyocr()
            elif self.config.PRIMARY_ENGINE == 'paddleocr':
                self._load_paddleocr()
            self._primary_loaded = True
            print(f"✓ {self.config.PRIMARY_ENGINE} loaded successfully")

    def _load_tesseract(self):
        """טעינת Tesseract OCR"""
        try:
            import pytesseract

            # חפש את Tesseract אוטומטית או השתמש בנתיב מוגדר
            tesseract_path = self.config.TESSERACT_PATH
            if tesseract_path is None:
                # נתיבים נפוצים ב-Windows
                common_paths = [
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                    r'C:\Tesseract-OCR\tesseract.exe',
                ]
                for path in common_paths:
                    if os.path.exists(path):
                        tesseract_path = path
                        break

            if tesseract_path and os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                print(f"  Using Tesseract at: {tesseract_path}")
            else:
                # נסה להשתמש ב-PATH
                print("  Looking for Tesseract in PATH...")

            # בדיקה שעברית מותקנת
            try:
                langs = pytesseract.get_languages()
                if 'heb' in langs:
                    print(f"  ✓ Hebrew language pack found")
                else:
                    print(f"  ⚠ Hebrew not found. Available: {langs}")
                    print(f"  Please install Hebrew language pack for Tesseract")
            except Exception as e:
                print(f"  ⚠ Could not check languages: {e}")

            self.primary_engine = pytesseract

        except ImportError:
            raise RuntimeError(
                "pytesseract not installed. Run: pip install pytesseract"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load Tesseract: {e}")

    def _load_easyocr(self):
        """טעינת EasyOCR עם retry logic"""
        import easyocr

        max_retries = 3
        retry_delay = 2  # שניות

        for attempt in range(max_retries):
            try:
                print(f"  Attempt {attempt + 1}/{max_retries}...")
                self.primary_engine = easyocr.Reader(
                    self.config.LANGUAGES,
                    gpu=self.config.GPU_ENABLED
                )
                return  # הצלחה!

            except PermissionError as e:
                if "temp.zip" in str(e):
                    print(f"  ⚠ temp.zip locked by another process")
                    if attempt < max_retries - 1:
                        print(f"  Waiting {retry_delay}s before retry...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # exponential backoff
                    else:
                        raise RuntimeError(
                            f"Failed to load EasyOCR after {max_retries} attempts.\n"
                            f"Suggestion: Close all Python processes and try again.\n"
                            f"Original error: {e}"
                        )
                else:
                    raise RuntimeError(f"Permission error loading EasyOCR: {e}")

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  ⚠ Error: {e}")
                    print(f"  Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise RuntimeError(
                        f"Failed to load EasyOCR after {max_retries} attempts: {e}"
                    )

    def _load_paddleocr(self):
        """טעינת PaddleOCR"""
        try:
            from paddleocr import PaddleOCR
            self.primary_engine = PaddleOCR(
                use_angle_cls=self.config.PADDLEOCR_USE_ANGLE_CLS,
                lang='he',
                use_gpu=self.config.PADDLEOCR_USE_GPU,
                show_log=self.config.PADDLEOCR_SHOW_LOG
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load PaddleOCR: {e}")

    def _load_fallback_engine(self):
        """טעינת מנוע fallback (רק כשצריך)"""
        if self._fallback_loaded:
            return

        # אם אין fallback מוגדר, לא עושים כלום
        if self.config.FALLBACK_ENGINE is None:
            print("  ℹ No fallback engine configured")
            self._fallback_loaded = True
            return

        print(f"Loading fallback engine: {self.config.FALLBACK_ENGINE}...")
        if self.config.FALLBACK_ENGINE == 'paddleocr':
            from paddleocr import PaddleOCR
            self.fallback_engine = PaddleOCR(
                use_angle_cls=self.config.PADDLEOCR_USE_ANGLE_CLS,
                lang='he',
                use_gpu=self.config.PADDLEOCR_USE_GPU,
                show_log=self.config.PADDLEOCR_SHOW_LOG
            )
        elif self.config.FALLBACK_ENGINE == 'easyocr':
            import easyocr
            self.fallback_engine = easyocr.Reader(
                self.config.LANGUAGES,
                gpu=self.config.GPU_ENABLED
            )
        self._fallback_loaded = True
        print(f"✓ Fallback engine loaded")

    def recognize_text(
        self,
        image: np.ndarray,
        use_fallback: bool = True
    ) -> OcrResult:
        """
        זיהוי טקסט עם fallback אוטומטי

        Args:
            image: תמונת המשבצת (numpy array, BGR)
            use_fallback: האם להשתמש ב-fallback במקרה של confidence נמוך

        Returns:
            OcrResult: תוצאת הזיהוי
        """
        if not self._primary_loaded:
            self.initialize_engines()

        start_time = time.time()

        # ניסיון ראשון עם המנוע הראשי
        result = self._recognize_with_engine(
            image,
            self.primary_engine,
            self.config.PRIMARY_ENGINE
        )

        # בדיקה אם צריך fallback (רק אם יש fallback מוגדר)
        if (use_fallback and
            result.confidence < self.config.CONFIDENCE_THRESHOLD and
            self.config.FALLBACK_ENGINE is not None):

            self._load_fallback_engine()

            # אם יש fallback engine זמין
            if self.fallback_engine is not None:
                fallback_result = self._recognize_with_engine(
                    image,
                    self.fallback_engine,
                    self.config.FALLBACK_ENGINE
                )

                # בחירת התוצאה הטובה יותר
                if fallback_result.confidence > result.confidence:
                    fallback_result.fallback_triggered = True
                    fallback_result.processing_time = time.time() - start_time
                    return fallback_result

        result.processing_time = time.time() - start_time
        return result

    def _recognize_with_engine(
        self,
        image: np.ndarray,
        engine,
        engine_name: str
    ) -> OcrResult:
        """
        זיהוי עם מנוע ספציפי

        Args:
            image: תמונה
            engine: המנוע (Tesseract, EasyOCR או PaddleOCR)
            engine_name: שם המנוע

        Returns:
            OcrResult
        """
        try:
            if engine_name == 'tesseract':
                return self._recognize_tesseract(image, engine)
            elif engine_name == 'easyocr':
                return self._recognize_easyocr(image, engine)
            elif engine_name == 'paddleocr':
                return self._recognize_paddleocr(image, engine)
            else:
                raise ValueError(f"Unknown engine: {engine_name}")
        except Exception as e:
            return OcrResult(
                text="",
                confidence=0.0,
                engine_used=engine_name,
                bbox=[],
                fallback_triggered=False,
                processing_time=0.0,
                raw_result=str(e)
            )

    def _recognize_tesseract(self, image: np.ndarray, pytesseract) -> OcrResult:
        """זיהוי עם Tesseract OCR"""
        from PIL import Image

        # המרה ל-PIL Image אם צריך
        if isinstance(image, np.ndarray):
            # המרה מ-BGR ל-RGB
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            pil_image = Image.fromarray(image_rgb)
        else:
            pil_image = image

        # הגדרות Tesseract
        lang = self.config.TESSERACT_LANG
        config = self.config.TESSERACT_CONFIG

        # זיהוי טקסט
        text = pytesseract.image_to_string(pil_image, lang=lang, config=config)
        text = text.strip()

        # קבלת נתוני confidence
        try:
            data = pytesseract.image_to_data(pil_image, lang=lang, config=config, output_type=pytesseract.Output.DICT)

            # חישוב confidence ממוצע (רק למילים שזוהו)
            confidences = [int(c) for c, t in zip(data['conf'], data['text']) if int(c) > 0 and t.strip()]
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

            # חילוץ bboxes
            bboxes = []
            for i, txt in enumerate(data['text']):
                if txt.strip() and int(data['conf'][i]) > 0:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    bboxes.append([[x, y], [x+w, y], [x+w, y+h], [x, y+h]])

        except Exception:
            avg_confidence = 0.5 if text else 0.0
            bboxes = []

        return OcrResult(
            text=text,
            confidence=avg_confidence,
            engine_used='tesseract',
            bbox=bboxes,
            raw_result={'text': text, 'lang': lang}
        )

    def _recognize_easyocr(self, image: np.ndarray, reader) -> OcrResult:
        """זיהוי עם EasyOCR"""
        results = reader.readtext(
            image,
            detail=self.config.EASYOCR_DETAIL,
            paragraph=self.config.EASYOCR_PARAGRAPH
        )

        if not results:
            return OcrResult(
                text="",
                confidence=0.0,
                engine_used='easyocr',
                bbox=[]
            )

        # EasyOCR מחזיר רשימה של (bbox, text, confidence)
        # נאחד את כל הטקסט
        all_text = []
        all_confidences = []
        all_bboxes = []

        for bbox, text, conf in results:
            all_text.append(text)
            all_confidences.append(conf)
            all_bboxes.append(bbox)

        combined_text = " ".join(all_text)
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        return OcrResult(
            text=combined_text,
            confidence=avg_confidence,
            engine_used='easyocr',
            bbox=all_bboxes,
            raw_result=results
        )

    def _recognize_paddleocr(self, image: np.ndarray, ocr) -> OcrResult:
        """זיהוי עם PaddleOCR"""
        results = ocr.ocr(image, cls=True)

        if not results or not results[0]:
            return OcrResult(
                text="",
                confidence=0.0,
                engine_used='paddleocr',
                bbox=[]
            )

        # PaddleOCR מחזיר מבנה מורכב יותר
        all_text = []
        all_confidences = []
        all_bboxes = []

        for line in results[0]:
            bbox, (text, conf) = line
            all_text.append(text)
            all_confidences.append(conf)
            all_bboxes.append(bbox)

        combined_text = " ".join(all_text)
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        return OcrResult(
            text=combined_text,
            confidence=avg_confidence,
            engine_used='paddleocr',
            bbox=all_bboxes,
            raw_result=results
        )

    def batch_recognize(
        self,
        images: List[np.ndarray],
        use_fallback: bool = True
    ) -> List[OcrResult]:
        """
        זיהוי batch של מספר תמונות

        Args:
            images: רשימת תמונות
            use_fallback: האם להשתמש ב-fallback

        Returns:
            רשימת תוצאות OCR
        """
        results = []
        for image in images:
            result = self.recognize_text(image, use_fallback)
            results.append(result)
        return results

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocessing של תמונה לפני OCR

        Args:
            image: תמונה מקורית

        Returns:
            תמונה מעובדת
        """
        processed = image.copy()

        # המרה ל-LAB ושיפור ניגודיות
        if self.config.ENHANCE_CONTRAST:
            lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            processed = cv2.merge((l, a, b))
            processed = cv2.cvtColor(processed, cv2.COLOR_LAB2BGR)

        # הסרת רעש
        if self.config.DENOISE:
            processed = cv2.fastNlMeansDenoisingColored(processed, None, 10, 10, 7, 21)

        # חידוד
        if self.config.SHARPEN:
            kernel = np.array([[-1, -1, -1],
                             [-1,  9, -1],
                             [-1, -1, -1]])
            processed = cv2.filter2D(processed, -1, kernel)

        return processed
