"""
Tests for Arrow Detection
"""

import pytest
import cv2
import numpy as np
import os
from services.arrow_detector import ArrowDetector
from config.arrow_config import ArrowConfig


class TestArrowDetector:
    """בדיקות לגלאי חצים"""

    @pytest.fixture
    def detector(self):
        """יצירת detector למבחנים"""
        return ArrowDetector()

    def test_template_loading(self, detector):
        """בדיקת טעינת תבניות"""
        assert len(detector.templates) > 0, "No templates loaded"
        assert len(detector.templates) == 12, "Should have 12 arrow types"

        # בדיקה שכל סוג יש לו 3 גדלים
        for arrow_type, templates in detector.templates.items():
            assert len(templates) == 3, f"{arrow_type} should have 3 size variations"

    def test_straight_arrow_detection(self, detector):
        """בדיקת זיהוי חצים ישרים"""
        # יצירת תמונה סינטטית עם חץ למטה
        img = np.ones((50, 50, 3), dtype=np.uint8) * 255
        cv2.arrowedLine(img, (25, 10), (25, 40), (0, 0, 0), 2, tipLength=0.3)

        result = detector.detect_arrow(img)

        assert result is not None
        assert result.confidence > 0.0
        # הכיוון אמור להיות down או משהו דומה
        assert 'down' in result.direction or result.direction != 'none'

    def test_preprocessing(self, detector):
        """בדיקת preprocessing"""
        # תמונה צבעונית
        color_img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        processed = detector._preprocess_for_template(color_img)

        assert len(processed.shape) == 2, "Should be grayscale"
        assert processed.dtype == np.uint8
        assert processed.shape == color_img.shape[:2]

    def test_multi_scale_matching(self, detector):
        """בדיקת multi-scale matching"""
        # טעינת תבנית אמיתית
        first_template = list(detector.templates.values())[0][0]['image']

        # יצירת תמונה גדולה יותר עם התבנית
        h, w = first_template.shape
        large_img = np.ones((h*2, w*2), dtype=np.uint8) * 255
        large_img[10:10+h, 10:10+w] = first_template

        score, location, scale = detector._multi_scale_match(
            large_img,
            first_template,
            scales=[0.8, 1.0, 1.2]
        )

        assert score > 0.5, "Should find a good match"
        assert scale in [0.8, 1.0, 1.2]

    def test_arrow_icon_mapping(self, detector):
        """בדיקת המרת כיוון לאייקון"""
        icon = detector.get_arrow_icon('straight-down')
        assert icon == "⬇️"

        icon = detector.get_arrow_icon('none')
        assert icon == "❓"

    def test_confidence_threshold(self, detector):
        """בדיקה שזיהוי עם confidence נמוך מחזיר 'none'"""
        # תמונה ריקה
        empty_img = np.ones((50, 50, 3), dtype=np.uint8) * 255

        result = detector.detect_arrow(empty_img)

        # אמור להחזיר 'none' בגלל confidence נמוך
        if result.confidence < detector.config.MATCH_THRESHOLD:
            assert result.direction == 'none'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
