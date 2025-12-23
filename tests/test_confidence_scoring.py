"""
Tests for Confidence Scoring
"""

import pytest
import numpy as np
from services.confidence_scorer import ConfidenceScorer
from models.recognition_result import (
    OcrResult,
    ArrowResult,
    ConfidenceLevel
)


class TestConfidenceScorer:
    """בדיקות למחשב ציוני ביטחון"""

    @pytest.fixture
    def scorer(self):
        """יצירת scorer למבחנים"""
        return ConfidenceScorer()

    def test_confidence_calculation(self, scorer):
        """בדיקת חישוב ציון ביטחון"""
        ocr_result = OcrResult(
            text="עיר בצפון",
            confidence=0.9,
            engine_used='easyocr'
        )

        arrow_result = ArrowResult(
            direction='straight-down',
            confidence=0.85
        )

        # ללא תמונה
        score = scorer.calculate_confidence(ocr_result, arrow_result, image=None)

        assert score.overall >= 0.0 and score.overall <= 1.0
        assert score.ocr_confidence > 0.0
        assert score.arrow_confidence > 0.0
        assert isinstance(score.level, ConfidenceLevel)

    def test_confidence_level_classification(self, scorer):
        """בדיקת סיווג לרמות"""
        # HIGH
        assert scorer._classify_confidence_level(0.9) == ConfidenceLevel.HIGH

        # MEDIUM
        assert scorer._classify_confidence_level(0.75) == ConfidenceLevel.MEDIUM

        # LOW
        assert scorer._classify_confidence_level(0.5) == ConfidenceLevel.LOW

    def test_image_quality_assessment(self, scorer):
        """בדיקת הערכת איכות תמונה"""
        # תמונה חדה
        sharp_img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        metrics = scorer.assess_image_quality(sharp_img)

        assert metrics.sharpness >= 0.0
        assert metrics.contrast >= 0.0 and metrics.contrast <= 1.0
        assert metrics.brightness >= 0.0 and metrics.brightness <= 255.0
        assert metrics.noise_level >= 0.0 and metrics.noise_level <= 1.0

    def test_sharpness_calculation(self, scorer):
        """בדיקת חישוב חדות"""
        # תמונה חדה (עם גרדיאנטים חדים)
        sharp = np.zeros((100, 100), dtype=np.uint8)
        sharp[:, :50] = 0
        sharp[:, 50:] = 255

        # תמונה מטושטשת (אחידה)
        blurry = np.ones((100, 100), dtype=np.uint8) * 128

        sharp_score = scorer._calculate_sharpness(sharp)
        blurry_score = scorer._calculate_sharpness(blurry)

        assert sharp_score > blurry_score

    def test_contrast_calculation(self, scorer):
        """בדיקת חישוב ניגודיות"""
        # ניגודיות גבוהה
        high_contrast = np.zeros((100, 100), dtype=np.uint8)
        high_contrast[:50, :] = 0
        high_contrast[50:, :] = 255

        # ניגודיות נמוכה
        low_contrast = np.ones((100, 100), dtype=np.uint8) * 100

        high_score = scorer._calculate_contrast(high_contrast)
        low_score = scorer._calculate_contrast(low_contrast)

        assert high_score > low_score

    def test_ocr_confidence_normalization(self, scorer):
        """בדיקת נרמול ציון OCR"""
        # מילה ארוכה
        long_word = OcrResult(
            text="מילה ארוכה מאוד",
            confidence=0.8,
            engine_used='easyocr',
            fallback_triggered=False
        )

        # מילה קצרה
        short_word = OcrResult(
            text="אב",
            confidence=0.8,
            engine_used='easyocr',
            fallback_triggered=False
        )

        long_norm = scorer._normalize_ocr_confidence(long_word)
        short_norm = scorer._normalize_ocr_confidence(short_word)

        # מילה ארוכה אמורה לקבל בונוס
        assert long_norm >= short_norm

    def test_arrow_confidence_normalization(self, scorer):
        """בדיקת נרמול ציון חץ"""
        # חץ ישר
        straight = ArrowResult(
            direction='straight-down',
            confidence=0.8
        )

        # חץ מדרגות
        step = ArrowResult(
            direction='start-left-turn-down',
            confidence=0.8
        )

        straight_norm = scorer._normalize_arrow_confidence(straight)
        step_norm = scorer._normalize_arrow_confidence(step)

        # חץ ישר אמור לקבל בונוס
        assert straight_norm >= step_norm

    def test_confidence_color(self, scorer):
        """בדיקת קבלת צבע לפי רמה"""
        high_color = scorer.get_confidence_color(ConfidenceLevel.HIGH)
        medium_color = scorer.get_confidence_color(ConfidenceLevel.MEDIUM)
        low_color = scorer.get_confidence_color(ConfidenceLevel.LOW)

        assert high_color.startswith("#")
        assert medium_color.startswith("#")
        assert low_color.startswith("#")
        assert high_color != medium_color != low_color


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
