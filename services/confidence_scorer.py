"""
Confidence Scorer
חישוב ציוני ביטחון משוקללים
"""

import cv2
import numpy as np
from typing import Dict

from config.confidence_config import ConfidenceConfig
from models.recognition_result import (
    OcrResult,
    ArrowResult,
    ImageQualityMetrics,
    ConfidenceScore,
    ConfidenceLevel
)


class ConfidenceScorer:
    """
    חישוב ציוני ביטחון משוקללים
    משלב OCR confidence, Arrow confidence ו-Image quality
    """

    def __init__(self, config: ConfidenceConfig = None):
        """
        Args:
            config: הגדרות ניקוד (אם None, משתמש בברירת מחדל)
        """
        self.config = config or ConfidenceConfig()

    def calculate_confidence(
        self,
        ocr_result: OcrResult,
        arrow_result: ArrowResult,
        image: np.ndarray = None
    ) -> ConfidenceScore:
        """
        חישוב ציון ביטחון כולל

        Args:
            ocr_result: תוצאת OCR
            arrow_result: תוצאת זיהוי חץ
            image: תמונת המשבצת (אופציונלי, לבדיקת איכות)

        Returns:
            ConfidenceScore: ציון ביטחון מלא
        """
        # הערכת איכות תמונה
        if image is not None:
            quality_metrics = self.assess_image_quality(image)
            quality_score = self._quality_metrics_to_score(quality_metrics)
        else:
            quality_metrics = ImageQualityMetrics(
                sharpness=0.0,
                contrast=0.0,
                brightness=0.0,
                noise_level=0.0
            )
            quality_score = 0.5  # ציון ברירת מחדל

        # נרמול ציוני OCR ו-Arrow
        ocr_conf = self._normalize_ocr_confidence(ocr_result)
        arrow_conf = self._normalize_arrow_confidence(arrow_result)

        # חישוב משוקלל
        overall = (
            self.config.WEIGHTS['ocr'] * ocr_conf +
            self.config.WEIGHTS['arrow'] * arrow_conf +
            self.config.WEIGHTS['quality'] * quality_score
        )

        # הגבלה ל-[0, 1]
        overall = max(0.0, min(1.0, overall))

        # סיווג לרמת ביטחון
        level = self._classify_confidence_level(overall)

        # רכיבים מפורטים
        has_image = image is not None
        components = {
            'ocr_raw': ocr_result.confidence,
            'ocr_normalized': ocr_conf,
            'arrow_raw': arrow_result.confidence,
            'arrow_normalized': arrow_conf,
            'quality_score': quality_score,
            'sharpness': quality_metrics.sharpness if has_image else 0.0,
            'contrast': quality_metrics.contrast if has_image else 0.0,
            'brightness': quality_metrics.brightness if has_image else 0.0,
            'noise_level': quality_metrics.noise_level if has_image else 0.0
        }

        return ConfidenceScore(
            overall=overall,
            ocr_confidence=ocr_conf,
            arrow_confidence=arrow_conf,
            image_quality=quality_score,
            level=level,
            components=components
        )

    def _normalize_ocr_confidence(self, ocr_result: OcrResult) -> float:
        """
        נרמול ציון OCR עם בונוסים

        Args:
            ocr_result: תוצאת OCR

        Returns:
            ציון מנורמל [0, 1]
        """
        base_conf = ocr_result.confidence

        # בונוס למילים ארוכות (יותר מהימנות)
        word_length = len(ocr_result.text.strip())
        if word_length > 5:
            base_conf += self.config.OCR_WORD_LENGTH_BONUS

        # בונוס אם המנוע לא נאלץ ל-fallback
        if not ocr_result.fallback_triggered:
            base_conf += 0.05

        return max(0.0, min(1.0, base_conf))

    def _normalize_arrow_confidence(self, arrow_result: ArrowResult) -> float:
        """
        נרמול ציון זיהוי חץ

        Args:
            arrow_result: תוצאת זיהוי חץ

        Returns:
            ציון מנורמל [0, 1]
        """
        base_conf = arrow_result.confidence

        # בונוס לחצים ישרים (יותר פשוטים לזיהוי = יותר מהימנים)
        if arrow_result.direction.startswith('straight'):
            base_conf += 0.05

        return max(0.0, min(1.0, base_conf))

    def _classify_confidence_level(self, score: float) -> ConfidenceLevel:
        """
        סיווג ציון לרמת ביטחון

        Args:
            score: ציון כולל [0, 1]

        Returns:
            ConfidenceLevel
        """
        if score >= self.config.THRESHOLDS['HIGH']:
            return ConfidenceLevel.HIGH
        elif score >= self.config.THRESHOLDS['MEDIUM']:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def assess_image_quality(self, image: np.ndarray) -> ImageQualityMetrics:
        """
        הערכת איכות תמונה

        Args:
            image: תמונת משבצת

        Returns:
            ImageQualityMetrics: מדדי איכות
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        sharpness = self._calculate_sharpness(gray)
        contrast = self._calculate_contrast(gray)
        brightness = self._calculate_brightness(gray)
        noise_level = self._calculate_noise(gray)

        return ImageQualityMetrics(
            sharpness=sharpness,
            contrast=contrast,
            brightness=brightness,
            noise_level=noise_level
        )

    def _calculate_sharpness(self, gray_image: np.ndarray) -> float:
        """
        חישוב חדות תמונה באמצעות Laplacian variance

        Args:
            gray_image: תמונה grayscale

        Returns:
            ציון חדות (ככל שגבוה יותר, כך טוב יותר)
        """
        laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
        variance = laplacian.var()
        return float(variance)

    def _calculate_contrast(self, gray_image: np.ndarray) -> float:
        """
        חישוב ניגודיות באמצעות Michelson contrast

        Args:
            gray_image: תמונה grayscale

        Returns:
            ציון ניגודיות [0, 1]
        """
        max_intensity = gray_image.max()
        min_intensity = gray_image.min()

        if max_intensity + min_intensity == 0:
            return 0.0

        contrast = (max_intensity - min_intensity) / (max_intensity + min_intensity)
        return float(contrast)

    def _calculate_brightness(self, gray_image: np.ndarray) -> float:
        """
        חישוב בהירות ממוצעת

        Args:
            gray_image: תמונה grayscale

        Returns:
            בהירות ממוצעת [0, 255]
        """
        return float(gray_image.mean())

    def _calculate_noise(self, gray_image: np.ndarray) -> float:
        """
        הערכת רמת רעש

        Args:
            gray_image: תמונה grayscale

        Returns:
            אומדן רעש [0, 1] (ככל שנמוך יותר, כך טוב יותר)
        """
        # שימוש ב-standard deviation כאומדן רעש
        # תמונה חלקה = רעש נמוך, תמונה רועשת = רעש גבוה
        h, w = gray_image.shape

        # חישוב gradient
        gx = cv2.Sobel(gray_image, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray_image, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gx**2 + gy**2)

        # רעש = סטיית תקן של הגרדיאנט מנורמלת
        noise = gradient_magnitude.std() / 255.0
        return float(min(noise, 1.0))

    def _quality_metrics_to_score(self, metrics: ImageQualityMetrics) -> float:
        """
        המרת מדדי איכות לציון יחיד [0, 1]

        Args:
            metrics: מדדי איכות

        Returns:
            ציון איכות כולל
        """
        # נרמול כל מדד
        sharpness_norm = min(metrics.sharpness / 500.0, 1.0)  # 500 = ערך טוב
        contrast_norm = metrics.contrast
        brightness_norm = 1.0 - abs(metrics.brightness - 128) / 128.0  # אופטימלי = 128
        noise_norm = 1.0 - metrics.noise_level  # פחות רעש = טוב יותר

        # שקלול
        quality_score = (
            self.config.QUALITY_WEIGHTS['sharpness'] * sharpness_norm +
            self.config.QUALITY_WEIGHTS['contrast'] * contrast_norm +
            self.config.QUALITY_WEIGHTS['brightness'] * brightness_norm +
            self.config.QUALITY_WEIGHTS['noise'] * noise_norm
        )

        return max(0.0, min(1.0, quality_score))

    def get_confidence_color(self, level: ConfidenceLevel) -> str:
        """
        קבלת צבע לרמת ביטחון (לתצוגה ב-UI)

        Args:
            level: רמת ביטחון

        Returns:
            קוד צבע hex
        """
        colors = {
            ConfidenceLevel.HIGH: "#28a745",    # ירוק
            ConfidenceLevel.MEDIUM: "#ffc107",  # צהוב
            ConfidenceLevel.LOW: "#dc3545"      # אדום
        }
        return colors.get(level, "#6c757d")  # אפור כברירת מחדל
