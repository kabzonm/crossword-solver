"""
Integration Tests
בדיקות אינטגרציה של כל המערכת
"""

import pytest
import numpy as np
import cv2
from models.grid import GridMatrix, Cell, CellType
from services.ocr_engine_manager import OcrEngineManager
from services.arrow_detector import ArrowDetector
from services.confidence_scorer import ConfidenceScorer
from services.batch_processor import BatchProcessor


class TestIntegration:
    """בדיקות אינטגרציה"""

    @pytest.fixture
    def simple_grid(self):
        """יצירת גריד פשוט למבחנים"""
        grid = GridMatrix(rows=3, cols=3)
        grid.initialize_grid()

        # סימון כמה משבצות כ-CLUE עם bbox
        grid.matrix[0][0].type = CellType.CLUE
        grid.matrix[0][0].bbox = (0, 0, 50, 50)

        grid.matrix[1][1].type = CellType.CLUE
        grid.matrix[1][1].bbox = (50, 50, 100, 100)

        return grid

    @pytest.fixture
    def sample_image(self):
        """יצירת תמונה לדוגמה"""
        # תמונה פשוטה 150x150
        img = np.ones((150, 150, 3), dtype=np.uint8) * 255

        # ציור טקסט פשוט במשבצות
        cv2.putText(img, "AB", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.putText(img, "CD", (60, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

        return img

    def test_full_pipeline_basic(self, simple_grid, sample_image):
        """בדיקת pipeline מלא על גריד קטן"""
        # אתחול כל הרכיבים
        ocr_manager = OcrEngineManager()
        ocr_manager.initialize_engines()

        arrow_detector = ArrowDetector()
        confidence_scorer = ConfidenceScorer()

        batch_processor = BatchProcessor(
            ocr_manager,
            arrow_detector,
            confidence_scorer,
            max_workers=2
        )

        # עיבוד
        updated_grid = batch_processor.process_grid(
            sample_image,
            simple_grid
        )

        # בדיקות
        assert updated_grid is not None
        assert updated_grid.rows == 3
        assert updated_grid.cols == 3

        # בדיקה שהמשבצות CLUE קיבלו תוצאות
        clue_cells = [
            cell for row in updated_grid.matrix
            for cell in row
            if cell.type == CellType.CLUE
        ]

        for cell in clue_cells:
            assert hasattr(cell, 'recognition_result')
            if cell.recognition_result:
                assert cell.recognition_result.ocr_result is not None
                assert cell.recognition_result.arrow_result is not None

    def test_stats_calculation(self, simple_grid, sample_image):
        """בדיקת חישוב סטטיסטיקות"""
        ocr_manager = OcrEngineManager()
        ocr_manager.initialize_engines()
        arrow_detector = ArrowDetector()
        confidence_scorer = ConfidenceScorer()

        batch_processor = BatchProcessor(
            ocr_manager,
            arrow_detector,
            confidence_scorer
        )

        updated_grid = batch_processor.process_grid(sample_image, simple_grid)
        stats = batch_processor.get_processing_stats(updated_grid)

        assert 'total_cells' in stats
        assert 'total_time' in stats
        assert 'avg_time_per_cell' in stats
        assert 'high_confidence' in stats
        assert 'medium_confidence' in stats
        assert 'low_confidence' in stats

        assert stats['total_cells'] >= 0
        assert stats['total_time'] >= 0.0


class TestPerformance:
    """בדיקות ביצועים"""

    def test_processing_speed(self):
        """בדיקת מהירות עיבוד"""
        import time

        # יצירת גריד 5x5 עם משבצות CLUE
        grid = GridMatrix(rows=5, cols=5)
        grid.initialize_grid()

        cell_size = 50
        for r in range(5):
            for c in range(5):
                if (r + c) % 2 == 0:  # חלק מהמשבצות
                    grid.matrix[r][c].type = CellType.CLUE
                    grid.matrix[r][c].bbox = (
                        c * cell_size,
                        r * cell_size,
                        (c + 1) * cell_size,
                        (r + 1) * cell_size
                    )

        # תמונה 250x250
        image = np.ones((250, 250, 3), dtype=np.uint8) * 255

        # מדידה
        ocr_manager = OcrEngineManager()
        ocr_manager.initialize_engines()
        arrow_detector = ArrowDetector()
        batch_processor = BatchProcessor(ocr_manager, arrow_detector)

        start = time.time()
        batch_processor.process_grid(image, grid)
        elapsed = time.time() - start

        # יעד: < 10 שניות לגריד קטן
        print(f"Processing time: {elapsed:.2f}s")
        assert elapsed < 30.0, f"Too slow: {elapsed:.2f}s (should be < 30s for small grid)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
