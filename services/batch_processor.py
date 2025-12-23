"""
Batch Processor
עיבוד מקבילי של משבצות גריד
"""

import time
import numpy as np
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

from models.grid import GridMatrix, Cell, CellType
from models.recognition_result import CellRecognitionResult
from services.ocr_engine_manager import OcrEngineManager
from services.arrow_detector import ArrowDetector
from services.confidence_scorer import ConfidenceScorer


class BatchProcessor:
    """
    עיבוד מקבילי של משבצות גריד
    משלב OCR, Arrow Detection ו-Confidence Scoring
    """

    def __init__(
        self,
        ocr_manager: OcrEngineManager,
        arrow_detector: ArrowDetector,
        confidence_scorer: ConfidenceScorer = None,
        max_workers: int = None
    ):
        """
        Args:
            ocr_manager: מנהל OCR
            arrow_detector: גלאי חצים
            confidence_scorer: מחשב ביטחון (אם None, יוצר אחד חדש)
            max_workers: מספר threads (None = cpu_count)
        """
        self.ocr_manager = ocr_manager
        self.arrow_detector = arrow_detector
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        self.max_workers = max_workers or cpu_count()

    def process_grid(
        self,
        original_image: np.ndarray,
        grid: GridMatrix,
        progress_callback: Callable[[float], None] = None
    ) -> GridMatrix:
        """
        עיבוד כל משבצות הגריד במקביל

        Args:
            original_image: התמונה המקורית (BGR)
            grid: אובייקט הגריד עם bbox לכל משבצת
            progress_callback: פונקציה לעדכון התקדמות (מקבלת float 0-1)

        Returns:
            GridMatrix מעודכן עם תוצאות הזיהוי
        """
        start_time = time.time()

        # הכנת tasks - רק למשבצות CLUE
        tasks = self._prepare_tasks(original_image, grid)

        if not tasks:
            print("No CLUE cells to process")
            # הוספת דיבוג - כמה תאים מכל סוג יש?
            clue_count = sum(1 for r in range(grid.rows) for c in range(grid.cols)
                           if grid.matrix[r][c].type == CellType.CLUE)
            bbox_count = sum(1 for r in range(grid.rows) for c in range(grid.cols)
                           if hasattr(grid.matrix[r][c], 'bbox'))
            print(f"  Debug: Total CLUE cells: {clue_count}, Cells with bbox: {bbox_count}")

            import streamlit as st
            st.warning(f"לא נמצאו משבצות הגדרה (CLUE) לעיבוד! (CLUE: {clue_count}, bbox: {bbox_count})")
            return grid

        print(f"Processing {len(tasks)} cells with {self.max_workers} workers...")
        import streamlit as st
        st.info(f"מעבד {len(tasks)} משבצות הגדרה...")

        # עיבוד מקבילי
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # שליחת כל ה-tasks
            future_to_task = {
                executor.submit(self._process_single_cell, task): task
                for task in tasks
            }

            # איסוף תוצאות
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

                # עדכון progress
                completed += 1
                if progress_callback:
                    progress_callback(completed / len(tasks))

        # עדכון הגריד עם התוצאות
        self._update_grid_with_results(grid, results)

        total_time = time.time() - start_time
        print(f"✓ Batch processing completed in {total_time:.2f}s")
        print(f"  Average time per cell: {total_time / len(tasks):.3f}s")

        return grid

    def _prepare_tasks(self, original_image: np.ndarray, grid: GridMatrix) -> list:
        """
        הכנת רשימת tasks לעיבוד

        Args:
            original_image: תמונה מקורית
            grid: הגריד

        Returns:
            רשימת dictionaries עם מידע לכל task
        """
        tasks = []

        for r in range(grid.rows):
            for c in range(grid.cols):
                cell = grid.matrix[r][c]

                # מעבד רק משבצות CLUE
                if cell.type == CellType.CLUE and hasattr(cell, 'bbox'):
                    x1, y1, x2, y2 = cell.bbox

                    # חיתוך ROI
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
        """
        עיבוד משבצת בודדת (OCR + Arrow + Confidence)

        Args:
            task: מידע על המשבצת

        Returns:
            CellRecognitionResult
        """
        start_time = time.time()
        cell_image = task['image']
        cell_bbox = task['bbox']
        row, col = task['row'], task['col']

        try:
            # 1. OCR
            print(f"  [{row},{col}] Starting OCR...")
            preprocessed_image = self.ocr_manager.preprocess_image(cell_image)
            ocr_result = self.ocr_manager.recognize_text(preprocessed_image)
            print(f"  [{row},{col}] OCR done: text='{ocr_result.text[:30] if ocr_result.text else ''}' conf={ocr_result.confidence:.2f}")

            # 2. Arrow Detection
            print(f"  [{row},{col}] Starting Arrow detection...")
            arrow_result = self.arrow_detector.detect_arrow(cell_image, cell_bbox)
            print(f"  [{row},{col}] Arrow done: dir={arrow_result.direction} conf={arrow_result.confidence:.2f}")

            # 3. Confidence Scoring
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
        """
        עדכון הגריד עם התוצאות

        Args:
            grid: הגריד המקורי
            results: dict של תוצאות {(row, col): CellRecognitionResult}
        """
        print(f"Updating grid with {len(results)} results...")
        updated_count = 0

        for (row, col), result in results.items():
            cell = grid.matrix[row][col]

            # שמירת התוצאה על התא
            cell.recognition_result = result

            # יצירת parsed_clues בפורמט הישן - תמיד יוצרים, גם אם אין תוצאה
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

            # אתחול parsed_clues אם לא קיים
            if not hasattr(cell, 'parsed_clues') or cell.parsed_clues is None:
                cell.parsed_clues = []
            cell.parsed_clues.append(clue_dict)
            updated_count += 1

            # דיבוג - הצג כמה תאים מעודכנים
            if updated_count <= 3:
                print(f"  Cell ({row},{col}): text='{ocr_text[:20]}...' conf={overall_conf:.2f}")

            # שמירת תמונה לדיבוג
            if result.cell_image is not None:
                import cv2
                import base64
                _, buffer = cv2.imencode('.png', result.cell_image)
                b64_img = base64.b64encode(buffer).decode('utf-8')
                cell.debug_image = f"data:image/png;base64,{b64_img}"

        print(f"✓ Updated {updated_count} cells with parsed_clues")

    def get_processing_stats(self, grid: GridMatrix) -> dict:
        """
        חישוב סטטיסטיקות על העיבוד

        Args:
            grid: הגריד המעובד

        Returns:
            dict עם מדדים
        """
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
