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
from services.split_cell_analyzer import SplitCellAnalyzer
from services.arrow_offset_calculator import ArrowOffsetCalculator
from config.cloud_config import get_cloud_config


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

        # SplitCellAnalyzer לניתוח משבצות חצויות - משתמש ב-Gemini 3 Pro
        config = get_cloud_config()
        self.split_analyzer = SplitCellAnalyzer(
            config=config.gemini  # Gemini config עם API key ומודל
        ) if config.gemini.api_key else None

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
                        # הרחבה של 27% לכל צד - מאזן בין לראות חצים לבין לא להכניס שכנים
                        arrow_expand_x = int(cell_w * 0.27)  # 27% הרחבה לכל צד
                        arrow_expand_y = int(cell_h * 0.27)

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
            print(f"\n{'='*50}")
            print(f"  [{row},{col}] === START PROCESSING ===")
            print(f"    Cell image: {cell_image.shape}, Arrow image: {arrow_image.shape}")
            ocr_result, arrow_results, is_split_cell = self.orchestrator.recognize_cell(
                cell_image,  # תמונה מדויקת ל-OCR (Google Vision)
                cell_bbox,
                arrow_image=arrow_image  # תמונה מורחבת לחצים (Claude)
            )
            print(f"  [{row},{col}] OCR: '{ocr_result.text[:20] if ocr_result.text else ''}' ({ocr_result.confidence:.2f})")
            print(f"  [{row},{col}] Arrows: {len(arrow_results)} found, is_split_cell={is_split_cell}")
            for i, ar in enumerate(arrow_results):
                print(f"    Arrow {i+1}: {ar.direction} ({ar.confidence:.2f}) | exit_side={ar.exit_side}, arrowhead={ar.arrowhead_direction}")
            print(f"  [{row},{col}] === END PROCESSING ===")
            print(f"{'='*50}\n")

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
                is_split_cell=is_split_cell,
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
        split_cells_analyzed = 0

        for (row, col), result in results.items():
            cell = grid.matrix[row][col]
            cell.recognition_result = result

            ocr_text = result.ocr_result.text if result.ocr_result else ""
            ocr_conf = result.ocr_result.confidence if result.ocr_result else 0.0
            overall_conf = result.confidence.overall if result.confidence else 0.0

            if not hasattr(cell, 'parsed_clues') or cell.parsed_clues is None:
                cell.parsed_clues = []

            # סינון משבצות ריקות - אם אין טקסט משמעותי, לא מוסיפים להגדרות
            clean_text = ocr_text.strip() if ocr_text else ""
            if not clean_text or len(clean_text) < 2:
                print(f"  [{row},{col}] Skipping empty cell (no meaningful text)")
                continue

            # יצירת שורה נפרדת לכל חץ שזוהה
            arrow_results = result.arrow_results or []

            if not arrow_results:
                # אין חצים - יוצרים שורה אחת עם 'none'
                clue_dict = self._create_clue_dict(
                    ocr_text, 'none', 'unknown', 'full',
                    overall_conf, ocr_conf, 0.0, row, col, grid
                )
                cell.parsed_clues.append(clue_dict)
                total_clues += 1

            # זיהוי משבצת חצויה: או is_split_cell=True, או 2 חצים
            elif (result.is_split_cell or len(arrow_results) == 2) and self.split_analyzer:
                # משבצת חצויה! קריאה לקלוד לפיצול
                reason = "is_split_cell flag" if result.is_split_cell else "2 arrows detected"
                print(f"  [{row},{col}] Split cell detected ({reason})! Analyzing...")
                split_cells_analyzed += 1

                # שמירת מידע החצים המקוריים כולל exit_side ו-arrowhead
                arrows_info = [
                    {
                        'direction': a.direction,
                        'position': a.position,
                        'confidence': a.confidence,
                        'exit_side': a.exit_side,
                        'arrowhead_direction': a.arrowhead_direction
                    }
                    for a in arrow_results
                ]

                split_result = self.split_analyzer.analyze_split_cell(
                    result.arrow_image if result.arrow_image is not None else result.cell_image,
                    ocr_text,
                    arrows_info
                )

                if split_result.definitions and len(split_result.definitions) == 2:
                    # הצלחנו לפצל!
                    print(f"  [{row},{col}] Split successful: {split_result.split_type}")
                    for i, defn in enumerate(split_result.definitions):
                        zone = defn.position  # "top"/"bottom"/"left"/"right"
                        # לקחת exit_side ו-arrowhead מהחץ המתאים
                        arrow_info = arrows_info[i] if i < len(arrows_info) else {}
                        clue_dict = self._create_clue_dict(
                            defn.text,
                            defn.arrow_direction,
                            defn.position,  # מיקום החץ = מיקום ההגדרה
                            zone,
                            overall_conf,
                            ocr_conf,
                            defn.confidence,
                            row, col, grid,
                            exit_side=arrow_info.get('exit_side'),
                            arrowhead_direction=arrow_info.get('arrowhead_direction')
                        )
                        cell.parsed_clues.append(clue_dict)
                        total_clues += 1
                else:
                    # לא הצלחנו לפצל - fallback, משתמשים בחצים המקוריים
                    print(f"  [{row},{col}] Split failed, using fallback with original arrows")
                    for i, arrow in enumerate(arrow_results):
                        # חלוקת הטקסט לשניים (פשוט)
                        text_parts = ocr_text.split('\n') if '\n' in ocr_text else [ocr_text, ocr_text]
                        text = text_parts[i] if i < len(text_parts) else ocr_text
                        clue_dict = self._create_clue_dict(
                            text,
                            arrow.direction,
                            arrow.position,
                            arrow.position,
                            overall_conf,
                            ocr_conf,
                            arrow.confidence,
                            row, col, grid,
                            exit_side=arrow.exit_side,
                            arrowhead_direction=arrow.arrowhead_direction
                        )
                        cell.parsed_clues.append(clue_dict)
                        total_clues += 1

            else:
                # 1 חץ רגיל - שורה נפרדת לכל חץ
                for arrow in arrow_results:
                    clue_dict = self._create_clue_dict(
                        ocr_text,
                        arrow.direction,
                        arrow.position,
                        'full',
                        overall_conf,
                        ocr_conf,
                        arrow.confidence,
                        row, col, grid,
                        exit_side=arrow.exit_side,
                        arrowhead_direction=arrow.arrowhead_direction
                    )
                    cell.parsed_clues.append(clue_dict)
                    total_clues += 1

            # שמירת תמונות דיבוג
            self._save_debug_images(cell, result)

            updated_count += 1

            if updated_count <= 3:
                arrows_str = ', '.join([a.direction for a in arrow_results]) if arrow_results else 'none'
                print(f"  Cell ({row},{col}): text='{ocr_text[:20]}...' arrows=[{arrows_str}]")

        print(f"[OK] Updated {updated_count} cells with {total_clues} parsed_clues")
        if split_cells_analyzed > 0:
            print(f"  Split cells analyzed: {split_cells_analyzed}")

    def _create_clue_dict(
        self,
        text: str,
        arrow_direction: str,
        arrow_position: str,
        zone: str,
        overall_conf: float,
        ocr_conf: float,
        arrow_conf: float,
        row: int,
        col: int,
        grid: GridMatrix,
        exit_side: str = None,
        arrowhead_direction: str = None
    ) -> dict:
        """יוצר dict של הגדרה עם חישוב אופסט"""
        # בניית כיוון חץ מורכב מ-exit_side ו-arrowhead_direction
        # לדוגמה: exit_side=left, arrowhead=down -> "left-down"
        effective_direction = self._compute_effective_direction(
            arrow_direction, exit_side, arrowhead_direction
        )

        # חישוב אופסט - משתמש בכיוון המורכב
        start_row, start_col, writing_dir = ArrowOffsetCalculator.calculate_answer_start(
            row, col, effective_direction
        )

        # חישוב אורך התשובה
        answer_length = 0
        start_cell_type = None
        if 0 <= start_row < grid.rows and 0 <= start_col < grid.cols:
            start_cell_type = grid.matrix[start_row][start_col].type
            if start_cell_type == CellType.SOLUTION:
                answer_length = self._count_answer_length(grid, start_row, start_col, writing_dir)

        # === לוג מפורט לדיבוג ===
        self._log_offset_calculation(
            row, col, text, arrow_direction, arrow_position,
            start_row, start_col, writing_dir, answer_length, start_cell_type,
            exit_side, arrowhead_direction, effective_direction
        )

        return {
            'text': text,
            'path': arrow_direction,
            'arrow_position': arrow_position,
            'zone': zone,
            'confidence': overall_conf,
            'ocr_confidence': ocr_conf,
            'arrow_confidence': arrow_conf,
            # מידע אופסט חדש
            'answer_start': (start_row, start_col) if answer_length > 0 else None,
            'writing_direction': writing_dir.value if writing_dir else None,
            'answer_length': answer_length
        }

    def _compute_effective_direction(
        self,
        arrow_direction: str,
        exit_side: str = None,
        arrowhead_direction: str = None
    ) -> str:
        """
        מחשב את כיוון החץ האפקטיבי מ-exit_side ו-arrowhead_direction.

        לוגיקה:
        - אם יש exit_side ו-arrowhead_direction שונים, זה חץ L-shaped
        - exit_side קובע את האופסט (מאיפה יוצא החץ)
        - arrowhead_direction קובע את כיוון הכתיבה (לאן מצביע ראש החץ)

        דוגמאות:
        - exit_side=left, arrowhead=down -> "left-down" (אופסט שמאלה, כתיבה למטה)
        - exit_side=bottom, arrowhead=right -> "down-right" (אופסט למטה, כתיבה ימינה)
        - exit_side=right, arrowhead=right -> "right" (חץ פשוט ימינה)
        """
        # נרמול ערכים
        exit_side = (exit_side or "").lower().strip()
        arrowhead = (arrowhead_direction or "").lower().strip()
        direction = (arrow_direction or "").lower().strip()

        # המרת exit_side לכיוון
        exit_side_to_direction = {
            'left': 'left',
            'right': 'right',
            'top': 'up',
            'bottom': 'down',
            'up': 'up',
            'down': 'down',
        }

        exit_dir = exit_side_to_direction.get(exit_side, "")

        # אם יש exit_side ו-arrowhead שונים, זה חץ L-shaped
        if exit_dir and arrowhead and exit_dir != arrowhead:
            # בונים כיוון מורכב: exit_side-arrowhead
            # לדוגמה: left-down, right-up, down-right
            l_shaped_direction = f"{exit_dir}-{arrowhead}"
            print(f"    [EffectiveDir] L-shaped: exit_side={exit_side} ({exit_dir}), arrowhead={arrowhead} -> {l_shaped_direction}")
            return l_shaped_direction

        # אם יש רק exit_side, משתמשים בו
        if exit_dir:
            print(f"    [EffectiveDir] Simple from exit_side: {exit_side} -> {exit_dir}")
            return exit_dir

        # אם יש רק arrowhead, משתמשים בו
        if arrowhead:
            print(f"    [EffectiveDir] Simple from arrowhead: {arrowhead}")
            return arrowhead

        # fallback: משתמשים ב-arrow_direction המקורי
        print(f"    [EffectiveDir] Fallback to original: {direction}")
        return direction

    def _log_offset_calculation(
        self,
        row: int, col: int,
        text: str,
        arrow_direction: str,
        arrow_position: str,
        start_row: int, start_col: int,
        writing_dir,
        answer_length: int,
        start_cell_type,
        exit_side: str = None,
        arrowhead_direction: str = None,
        effective_direction: str = None
    ) -> None:
        """לוג מפורט של חישוב אופסט - לדיבוג"""
        # שמירה לרשימת לוגים
        if not hasattr(self, '_debug_logs'):
            self._debug_logs = []

        log_entry = {
            'source_cell': f"({row+1},{col+1})",
            'text': text[:30] if text else "(empty)",
            'exit_side': exit_side or "-",
            'arrowhead': arrowhead_direction or "-",
            'effective_direction': effective_direction or arrow_direction,
            'arrow_direction': arrow_direction,
            'arrow_position': arrow_position,
            'answer_start': f"({start_row+1},{start_col+1})",
            'writing_direction': writing_dir.value if writing_dir else "None",
            'answer_length': answer_length,
            'start_cell_type': start_cell_type.value if start_cell_type else "out_of_bounds",
            'status': 'OK' if answer_length > 0 else 'PROBLEM'
        }
        self._debug_logs.append(log_entry)

        # הדפסה לקונסול
        status = "✅" if answer_length > 0 else "❌"
        print(f"  {status} [{row+1},{col+1}] '{text[:20]}...'")
        print(f"      Raw: exit_side={exit_side}, arrowhead={arrowhead_direction}")
        print(f"      Effective direction: {effective_direction or arrow_direction}")
        print(f"      → Start: ({start_row+1},{start_col+1}), Dir: {writing_dir.value if writing_dir else 'None'}, Len: {answer_length}")
        if answer_length == 0:
            print(f"      ⚠ Start cell type: {start_cell_type.value if start_cell_type else 'OUT_OF_BOUNDS'}")

    def get_debug_logs(self) -> list:
        """מחזיר את רשימת הלוגים לדיבוג"""
        return getattr(self, '_debug_logs', [])

    def reexamine_cell(
        self,
        original_image: np.ndarray,
        grid: GridMatrix,
        row: int,
        col: int
    ) -> CellRecognitionResult:
        """
        בחינה חוזרת של משבצת בודדת.
        מאפשר לשלוח משבצת ספציפית לזיהוי מחדש.

        Args:
            original_image: התמונה המקורית (BGR)
            grid: אובייקט הגריד
            row: שורת המשבצת
            col: עמודת המשבצת

        Returns:
            CellRecognitionResult עם התוצאות החדשות
        """
        cell = grid.matrix[row][col]

        if cell.type != CellType.CLUE or not hasattr(cell, 'bbox'):
            print(f"[Reexamine] Cell ({row},{col}) is not a valid CLUE cell")
            return None

        img_h, img_w = original_image.shape[:2]
        x1, y1, x2, y2 = cell.bbox

        # חיתוך התמונה המדויקת
        cell_image = original_image[y1:y2, x1:x2].copy()
        if cell_image.size == 0:
            print(f"[Reexamine] Empty cell image for ({row},{col})")
            return None

        cell_w = x2 - x1
        cell_h = y2 - y1

        # תמונה מורחבת לזיהוי חצים (27% הרחבה)
        arrow_expand_x = int(cell_w * 0.27)
        arrow_expand_y = int(cell_h * 0.27)

        arrow_x1 = max(0, x1 - arrow_expand_x)
        arrow_y1 = max(0, y1 - arrow_expand_y)
        arrow_x2 = min(img_w, x2 + arrow_expand_x)
        arrow_y2 = min(img_h, y2 + arrow_expand_y)

        arrow_context_image = original_image[arrow_y1:arrow_y2, arrow_x1:arrow_x2].copy()

        # עיבוד המשבצת מחדש
        print(f"[Reexamine] Re-processing cell ({row},{col})...")
        task = {
            'row': row,
            'col': col,
            'image': cell_image,
            'arrow_image': arrow_context_image,
            'bbox': cell.bbox,
            'cell': cell
        }

        result = self._process_single_cell(task)

        # עדכון הגריד עם התוצאות החדשות
        if result:
            self._update_single_cell(grid, row, col, result)
            print(f"[Reexamine] Cell ({row},{col}) updated successfully")

        return result

    def _update_single_cell(self, grid: GridMatrix, row: int, col: int, result: CellRecognitionResult) -> None:
        """עדכון משבצת בודדת עם תוצאות חדשות"""
        cell = grid.matrix[row][col]
        cell.recognition_result = result

        ocr_text = result.ocr_result.text if result.ocr_result else ""
        ocr_conf = result.ocr_result.confidence if result.ocr_result else 0.0
        overall_conf = result.confidence.overall if result.confidence else 0.0

        # איפוס parsed_clues
        cell.parsed_clues = []

        arrow_results = result.arrow_results or []

        if not arrow_results:
            # אין חצים
            clue_dict = self._create_clue_dict(
                ocr_text, 'none', 'unknown', 'full',
                overall_conf, ocr_conf, 0.0, row, col, grid
            )
            cell.parsed_clues.append(clue_dict)

        elif (result.is_split_cell or len(arrow_results) == 2) and self.split_analyzer:
            # משבצת חצויה
            reason = "is_split_cell flag" if result.is_split_cell else "2 arrows detected"
            print(f"  [{row},{col}] Split cell detected ({reason})!")

            # שמירת מידע החצים המקוריים כולל exit_side ו-arrowhead
            arrows_info = [
                {
                    'direction': a.direction,
                    'position': a.position,
                    'confidence': a.confidence,
                    'exit_side': a.exit_side,
                    'arrowhead_direction': a.arrowhead_direction
                }
                for a in arrow_results
            ]

            split_result = self.split_analyzer.analyze_split_cell(
                result.arrow_image if result.arrow_image is not None else result.cell_image,
                ocr_text,
                arrows_info
            )

            if split_result.definitions and len(split_result.definitions) == 2:
                for i, defn in enumerate(split_result.definitions):
                    zone = defn.position
                    # לקחת exit_side ו-arrowhead מהחץ המתאים
                    arrow_info = arrows_info[i] if i < len(arrows_info) else {}
                    clue_dict = self._create_clue_dict(
                        defn.text,
                        defn.arrow_direction,
                        defn.position,
                        zone,
                        overall_conf,
                        ocr_conf,
                        defn.confidence,
                        row, col, grid,
                        exit_side=arrow_info.get('exit_side'),
                        arrowhead_direction=arrow_info.get('arrowhead_direction')
                    )
                    cell.parsed_clues.append(clue_dict)
            else:
                # fallback - משתמשים בחצים המקוריים
                print(f"  [{row},{col}] Split failed, using fallback with original arrows")
                for i, arrow in enumerate(arrow_results):
                    text_parts = ocr_text.split('\n') if '\n' in ocr_text else [ocr_text, ocr_text]
                    text = text_parts[i] if i < len(text_parts) else ocr_text
                    clue_dict = self._create_clue_dict(
                        text,
                        arrow.direction,
                        arrow.position,
                        arrow.position,
                        overall_conf,
                        ocr_conf,
                        arrow.confidence,
                        row, col, grid,
                        exit_side=arrow.exit_side,
                        arrowhead_direction=arrow.arrowhead_direction
                    )
                    cell.parsed_clues.append(clue_dict)

        else:
            # חץ רגיל
            for arrow in arrow_results:
                clue_dict = self._create_clue_dict(
                    ocr_text,
                    arrow.direction,
                    arrow.position,
                    'full',
                    overall_conf,
                    ocr_conf,
                    arrow.confidence,
                    row, col, grid,
                    exit_side=arrow.exit_side,
                    arrowhead_direction=arrow.arrowhead_direction
                )
                cell.parsed_clues.append(clue_dict)

        # שמירת תמונות דיבוג
        self._save_debug_images(cell, result)

    def clear_debug_logs(self) -> None:
        """מנקה את רשימת הלוגים"""
        self._debug_logs = []

    def _count_answer_length(self, grid: GridMatrix, start_row: int, start_col: int, writing_dir) -> int:
        """סופר כמה משבצות SOLUTION ברצף"""
        from models.clue_entry import WritingDirection

        if writing_dir is None:
            return 0

        d_row, d_col = {
            WritingDirection.DOWN: (1, 0),
            WritingDirection.UP: (-1, 0),
            WritingDirection.RIGHT: (0, 1),
            WritingDirection.LEFT: (0, -1),
        }.get(writing_dir, (0, 0))

        count = 0
        row, col = start_row, start_col

        while 0 <= row < grid.rows and 0 <= col < grid.cols:
            if grid.matrix[row][col].type != CellType.SOLUTION:
                break
            count += 1
            row += d_row
            col += d_col

        return count

    def _save_debug_images(self, cell: Cell, result: CellRecognitionResult) -> None:
        """שמירת תמונות לדיבוג"""
        import cv2
        import base64

        if result.cell_image is not None:
            _, buffer = cv2.imencode('.png', result.cell_image)
            b64_img = base64.b64encode(buffer).decode('utf-8')
            cell.debug_image = f"data:image/png;base64,{b64_img}"

        if result.arrow_image is not None:
            _, buffer = cv2.imencode('.png', result.arrow_image)
            b64_img = base64.b64encode(buffer).decode('utf-8')
            cell.arrow_debug_image = f"data:image/png;base64,{b64_img}"

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
