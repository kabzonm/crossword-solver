"""
OCR Service (Phase 1 - Refactored)
שירות OCR מחודש שמשתמש ב-Pipeline המקומי במקום GPT-4
"""

import cv2
import numpy as np
import streamlit as st
from models.grid import GridMatrix
from services.ocr_engine_manager import OcrEngineManager
from services.arrow_detector import ArrowDetector
from services.confidence_scorer import ConfidenceScorer
from services.batch_processor import BatchProcessor


class OcrService:
    """
    שירות OCR מחודש - Phase 1
    משתמש ב-EasyOCR/PaddleOCR + Template Matching במקום GPT-4
    """

    def __init__(self, use_local_ocr: bool = True):
        """
        Args:
            use_local_ocr: אם True, משתמש בפייפליין המקומי החדש
                          אם False, משתמש ב-GPT-4 הישן (fallback)
        """
        self.use_local_ocr = use_local_ocr

        if self.use_local_ocr:
            # Pipeline החדש
            print("Initializing Phase 1 OCR Pipeline...")
            self.ocr_manager = OcrEngineManager()
            self.ocr_manager.initialize_engines()
            self.arrow_detector = ArrowDetector()
            self.confidence_scorer = ConfidenceScorer()
            self.batch_processor = BatchProcessor(
                self.ocr_manager,
                self.arrow_detector,
                self.confidence_scorer
            )
            print("✓ Phase 1 Pipeline ready")
        else:
            # Fallback לקוד הישן (GPT-4)
            from services.ocr_service import OcrService as OldOcrService
            self._old_service = OldOcrService()

    def recognize_clues(self, original_image: np.ndarray, grid: GridMatrix):
        """
        זיהוי הגדרות במשבצות

        Args:
            original_image: התמונה המקורית
            grid: אובייקט הגריד

        Returns:
            GridMatrix מעודכן עם תוצאות הזיהוי
        """
        if self.use_local_ocr:
            return self._recognize_with_local_pipeline(original_image, grid)
        else:
            return self._old_service.recognize_clues(original_image, grid)

    def _recognize_with_local_pipeline(
        self,
        original_image: np.ndarray,
        grid: GridMatrix
    ) -> GridMatrix:
        """
        זיהוי עם Pipeline מקומי חדש
        """
        # דיבוג: הצגת מידע על הגריד
        from models.grid import CellType
        total_cells = grid.rows * grid.cols
        clue_cells = sum(1 for r in range(grid.rows) for c in range(grid.cols)
                        if grid.matrix[r][c].type == CellType.CLUE)
        bbox_cells = sum(1 for r in range(grid.rows) for c in range(grid.cols)
                        if hasattr(grid.matrix[r][c], 'bbox'))

        print(f"Grid info: {grid.rows}x{grid.cols} = {total_cells} cells")
        print(f"  CLUE cells: {clue_cells}")
        print(f"  Cells with bbox: {bbox_cells}")

        st.write(f"**דיבוג:** גריד {grid.rows}x{grid.cols}, משבצות CLUE: {clue_cells}, עם bbox: {bbox_cells}")

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

        # הצגת סטטיסטיקות
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

    def _path_to_icon(self, path: str) -> str:
        """
        המרת כיוון חץ לאייקון (תאימות לאחור)
        """
        return self.arrow_detector.get_arrow_icon(path)
