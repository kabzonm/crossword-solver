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

        print("[OK] OCR Service ready")

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

    def _path_to_icon(self, path: str) -> str:
        """
        המרת כיוון חץ לאייקון (תאימות לאחור)
        """
        from services.arrow_detector import ArrowDetector
        detector = ArrowDetector()
        return detector.get_arrow_icon(path)
