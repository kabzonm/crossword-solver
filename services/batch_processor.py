"""
Batch Processor - Updated for Phase 2
עיבוד מקבילי של משבצות גריד עם תמיכה ב-Cloud Services
"""

import time
import numpy as np
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

from models.grid import GridMatrix, Cell, CellType
from models.recognition_result import CellRecognitionResult
from services.recognition_orchestrator import RecognitionOrchestrator
from services.confidence_scorer import ConfidenceScorer


class BatchProcessor:
    """
    עיבוד מקבילי של משבצות גריד
    Phase 2: משתמש ב-RecognitionOrchestrator לתיאום בין השירותים
    """

    def __init__(
        self,
        orchestrator: RecognitionOrchestrator = None,
        confidence_scorer: ConfidenceScorer = None,
        max_workers: int = None
    ):
        """
        Args:
            orchestrator: מתאם הזיהוי (אם None, יוצר אחד חדש)
            confidence_scorer: מחשב ביטחון (אם None, יוצר אחד חדש)
            max_workers: מספר threads (None = cpu_count)
        """
        self.orchestrator = orchestrator or RecognitionOrchestrator()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()

        # מספר workers מותאם - פחות ב-cloud כי יש rate limits
        if max_workers is None:
            providers = self.orchestrator.get_active_providers()
            if providers.get('google_available') or providers.get('claude_available'):
                self.max_workers = min(4, cpu_count())  # הגבלה ל-4 לcloud
            else:
                self.max_workers = cpu_count()
        else:
            self.max_workers = max_workers

    def process_grid(
        self,
        original_image: np.ndarray,
        grid: GridMatrix,
        progress_callback: Callable[[float], None] = None
    ) -> GridMatrix:
        """
        עיבוד כל משבצות הגריד

        Args:
            original_image: התמונה המקורית (BGR)
            grid: אובייקט הגריד עם bbox לכל משבצת
            progress_callback: פונקציה לעדכון התקדמות

        Returns:
            GridMatrix מעודכן עם תוצאות הזיהוי
        """
        start_time = time.time()

        # הצגת ספקים פעילים
        providers = self.orchestrator.get_active_providers()
        print(f"Active providers: OCR={providers['text_ocr']}, Arrows={providers['arrow_detector']}")

        # הכנת tasks
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
            future_to_task = {
                executor.submit(self._process_single_cell, task): task
                for task in tasks
            }

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

                completed += 1
                if progress_callback:
                    progress_callback(completed / len(tasks))

        # עדכון הגריד
        self._update_grid_with_results(grid, results)

        total_time = time.time() - start_time
        print(f"[OK] Batch processing completed in {total_time:.2f}s")
        print(f"  Average time per cell: {total_time / len(tasks):.3f}s")

        return grid

    def _prepare_tasks(self, original_image: np.ndarray, grid: GridMatrix) -> list:
        """הכנת רשימת tasks לעיבוד"""
        tasks = []
        img_h, img_w = original_image.shape[:2]

        for r in range(grid.rows):
            for c in range(grid.cols):
                cell = grid.matrix[r][c]

                if cell.type == CellType.CLUE and hasattr(cell, 'bbox'):
                    x1, y1, x2, y2 = cell.bbox
                    cell_image = original_image[y1:y2, x1:x2].copy()

                    if cell_image.size > 0:
                        cell_w = x2 - x1
                        cell_h = y2 - y1

                        # תמונה מורחבת לזיהוי חצים עם Claude
                        # הרחבה קטנה של 30% לכל צד - מספיק לראות חץ בקצה
                        # בלי להכניס חצים מתאים שכנים שמבלבלים
                        arrow_expand_x = int(cell_w * 0.3)  # 30% הרחבה לכל צד
                        arrow_expand_y = int(cell_h * 0.3)

                        arrow_x1 = max(0, x1 - arrow_expand_x)
                        arrow_y1 = max(0, y1 - arrow_expand_y)
                        arrow_x2 = min(img_w, x2 + arrow_expand_x)
                        arrow_y2 = min(img_h, y2 + arrow_expand_y)

                        arrow_context_image = original_image[arrow_y1:arrow_y2, arrow_x1:arrow_x2].copy()

                        tasks.append({
                            'row': r,
                            'col': c,
                            'image': cell_image,  # תמונה מדויקת לזיהוי טקסט (OCR)
                            'arrow_image': arrow_context_image,  # תמונה מורחבת לזיהוי חצים (Claude)
                            'bbox': cell.bbox,
                            'cell': cell
                        })

        return tasks

    def _process_single_cell(self, task: dict) -> CellRecognitionResult:
        """עיבוד משבצת בודדת"""
        start_time = time.time()
        cell_image = task['image']  # תמונה מדויקת לזיהוי טקסט
        arrow_image = task.get('arrow_image', cell_image)  # תמונה מורחבת לזיהוי חצים
        cell_bbox = task['bbox']
        row, col = task['row'], task['col']

        try:
            # Phase 2: שימוש ב-Orchestrator
            print(f"  [{row},{col}] Processing with orchestrator...")
            print(f"    Cell image: {cell_image.shape}, Arrow image: {arrow_image.shape}")
            ocr_result, arrow_results = self.orchestrator.recognize_cell(
                cell_image,  # תמונה מדויקת ל-OCR (Google Vision)
                cell_bbox,
                arrow_image=arrow_image  # תמונה מורחבת לחצים (Claude)
            )
            print(f"  [{row},{col}] OCR: '{ocr_result.text[:20] if ocr_result.text else ''}' ({ocr_result.confidence:.2f})")
            print(f"  [{row},{col}] Arrows: {len(arrow_results)} found")
            for i, ar in enumerate(arrow_results):
                print(f"    Arrow {i+1}: {ar.direction} ({ar.confidence:.2f})")

            # Confidence Scoring - משתמש בחץ הראשון (הכי בטוח)
            primary_arrow = arrow_results[0] if arrow_results else None
            confidence_score = self.confidence_scorer.calculate_confidence(
                ocr_result,
                primary_arrow,
                cell_image
            )

            processing_time = time.time() - start_time

            return CellRecognitionResult(
                ocr_result=ocr_result,
                arrow_results=arrow_results,
                confidence=confidence_score,
                processing_time=processing_time,
                cell_image=cell_image,
                arrow_image=arrow_image
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
        """עדכון הגריד עם התוצאות - שורה נפרדת לכל חץ"""
        print(f"Updating grid with {len(results)} results...")
        updated_count = 0
        total_clues = 0

        for (row, col), result in results.items():
            cell = grid.matrix[row][col]
            cell.recognition_result = result

            ocr_text = result.ocr_result.text if result.ocr_result else ""
            ocr_conf = result.ocr_result.confidence if result.ocr_result else 0.0
            overall_conf = result.confidence.overall if result.confidence else 0.0

            if not hasattr(cell, 'parsed_clues') or cell.parsed_clues is None:
                cell.parsed_clues = []

            # יצירת שורה נפרדת לכל חץ שזוהה
            arrow_results = result.arrow_results or []

            if not arrow_results:
                # אין חצים - יוצרים שורה אחת עם 'none'
                clue_dict = {
                    'text': ocr_text,
                    'path': 'none',
                    'zone': 'full_cell',
                    'confidence': overall_conf,
                    'ocr_confidence': ocr_conf,
                    'arrow_confidence': 0.0
                }
                cell.parsed_clues.append(clue_dict)
                total_clues += 1
            else:
                # יש חצים - שורה נפרדת לכל חץ
                for arrow in arrow_results:
                    clue_dict = {
                        'text': ocr_text,
                        'path': arrow.direction,
                        'arrow_position': arrow.position,
                        'zone': 'full_cell',
                        'confidence': overall_conf,
                        'ocr_confidence': ocr_conf,
                        'arrow_confidence': arrow.confidence
                    }
                    cell.parsed_clues.append(clue_dict)
                    total_clues += 1

            updated_count += 1

            if updated_count <= 3:
                arrows_str = ', '.join([a.direction for a in arrow_results]) if arrow_results else 'none'
                print(f"  Cell ({row},{col}): text='{ocr_text[:20]}...' arrows=[{arrows_str}]")

            if result.cell_image is not None:
                import cv2
                import base64
                _, buffer = cv2.imencode('.png', result.cell_image)
                b64_img = base64.b64encode(buffer).decode('utf-8')
                cell.debug_image = f"data:image/png;base64,{b64_img}"

            # שמירת התמונה שנשלחה לקלוד (לדיבוג)
            if result.arrow_image is not None:
                import cv2
                import base64
                _, buffer = cv2.imencode('.png', result.arrow_image)
                b64_img = base64.b64encode(buffer).decode('utf-8')
                cell.arrow_debug_image = f"data:image/png;base64,{b64_img}"

        print(f"[OK] Updated {updated_count} cells with {total_clues} parsed_clues")

    def get_processing_stats(self, grid: GridMatrix) -> dict:
        """חישוב סטטיסטיקות על העיבוד"""
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

                    if result.arrow_results:
                        for arrow in result.arrow_results:
                            arrow_confidences.append(arrow.confidence)

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
