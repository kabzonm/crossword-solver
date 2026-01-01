"""
Arrow Detector
זיהוי כיוון חצים עם Template Matching
"""

import time
import cv2
import numpy as np
import os
from typing import Tuple, Dict, List, Optional
from functools import lru_cache

from config.arrow_config import ArrowConfig
from models.recognition_result import ArrowResult


class ArrowDetector:
    """
    זיהוי כיוון חצים עם Template Matching
    משתמש ב-12 תבניות חצים (כל אחת ב-3 גדלים)
    """

    # מיפוי מ-direction ל-exit_side ו-arrowhead
    DIRECTION_TO_RAW = {
        'straight-down': ('bottom', 'down'),
        'straight-up': ('top', 'up'),
        'straight-right': ('right', 'right'),
        'straight-left': ('left', 'left'),
        'start-down-turn-right': ('bottom', 'right'),
        'start-down-turn-left': ('bottom', 'left'),
        'start-up-turn-right': ('top', 'right'),
        'start-up-turn-left': ('top', 'left'),
        'start-right-turn-down': ('right', 'down'),
        'start-right-turn-up': ('right', 'up'),
        'start-left-turn-down': ('left', 'down'),
        'start-left-turn-up': ('left', 'up'),
        'none': (None, None),
    }

    def __init__(self, templates_path: str = None, config: ArrowConfig = None):
        """
        Args:
            templates_path: נתיב לתיקיית התבניות (אם None, לוקח מה-config)
            config: הגדרות (אם None, משתמש בברירת מחדל)
        """
        self.config = config or ArrowConfig()
        self.templates_path = templates_path or self.config.TEMPLATES_PATH
        self.templates = {}  # {arrow_type: [(template_img, size_name, scale), ...]}
        self._load_templates()

    def _load_templates(self) -> None:
        """
        טעינת כל תבניות החצים מהדיסק
        """
        if not os.path.exists(self.templates_path):
            raise FileNotFoundError(f"Templates directory not found: {self.templates_path}")

        print(f"Loading arrow templates from {self.templates_path}...")
        loaded_count = 0

        for arrow_type in self.config.ARROW_TYPES:
            self.templates[arrow_type] = []

            for size_name in self.config.TEMPLATE_SIZES:
                # בניית שם קובץ
                # straight-left → straight_left_small.png
                filename = f"{arrow_type.replace('-', '_')}_{size_name}.png"
                filepath = os.path.join(self.templates_path, filename)

                if os.path.exists(filepath):
                    template = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        self.templates[arrow_type].append({
                            'image': template,
                            'size_name': size_name,
                            'filename': filename
                        })
                        loaded_count += 1
                else:
                    print(f"Warning: Template not found: {filename}")

        print(f"✓ Loaded {loaded_count} arrow templates for {len(self.templates)} arrow types")

        if loaded_count == 0:
            raise RuntimeError("No templates loaded! Check templates directory.")

    def detect_arrow(
        self,
        cell_image: np.ndarray,
        cell_bbox: Tuple[int, int, int, int] = None
    ) -> ArrowResult:
        """
        זיהוי חץ במשבצת

        Args:
            cell_image: תמונת המשבצת (BGR)
            cell_bbox: קואורדינטות המשבצת (x1, y1, x2, y2) - אופציונלי

        Returns:
            ArrowResult: תוצאת הזיהוי
        """
        start_time = time.time()

        # Preprocessing
        preprocessed = self._preprocess_for_template(cell_image)

        # חיפוש בכל התבניות
        best_match = None
        best_score = 0.0
        best_location = (0, 0)
        best_template = None
        best_scale = 1.0

        for arrow_type, templates_list in self.templates.items():
            for template_dict in templates_list:
                template = template_dict['image']

                # Multi-scale matching
                score, location, scale = self._multi_scale_match(
                    preprocessed,
                    template,
                    self.config.SCALES
                )

                if score > best_score:
                    best_score = score
                    best_match = arrow_type
                    best_location = location
                    best_template = template_dict['filename']
                    best_scale = scale

        processing_time = time.time() - start_time

        # בדיקה אם עברנו את הסף
        if best_score < self.config.MATCH_THRESHOLD:
            # לא נמצא חץ מספיק טוב
            return ArrowResult(
                direction='none',
                confidence=best_score,
                match_location=best_location,
                scale_used=best_scale,
                processing_time=processing_time,
                template_matched=None,
                exit_side=None,
                arrowhead_direction=None
            )

        # חישוב exit_side ו-arrowhead מה-direction
        exit_side, arrowhead = self.DIRECTION_TO_RAW.get(best_match, (None, None))

        return ArrowResult(
            direction=best_match,
            confidence=best_score,
            match_location=best_location,
            scale_used=best_scale,
            processing_time=processing_time,
            template_matched=best_template,
            exit_side=exit_side,
            arrowhead_direction=arrowhead
        )

    def _preprocess_for_template(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocessing לזיהוי חצים

        Args:
            image: תמונה צבעונית

        Returns:
            תמונה בינארית מעובדת
        """
        # המרה ל-grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            self.config.ADAPTIVE_THRESH_BLOCK_SIZE,
            self.config.ADAPTIVE_THRESH_C
        )

        # ניקוי רעשים קטנים
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        return binary

    def _multi_scale_match(
        self,
        image: np.ndarray,
        template: np.ndarray,
        scales: List[float] = None
    ) -> Tuple[float, Tuple[int, int], float]:
        """
        Template matching בסקלות שונות

        Args:
            image: תמונת המשבצת
            template: תבנית החץ
            scales: רשימת סקלות לבדיקה

        Returns:
            (best_score, best_location, best_scale)
        """
        scales = scales or [1.0]
        best_score = 0.0
        best_location = (0, 0)
        best_scale = 1.0

        for scale in scales:
            # שינוי גודל התבנית
            scaled_template = cv2.resize(
                template,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_LINEAR
            )

            # בדיקה שהתבנית לא גדולה מהתמונה
            if (scaled_template.shape[0] > image.shape[0] or
                scaled_template.shape[1] > image.shape[1]):
                continue

            # Template matching
            try:
                result = cv2.matchTemplate(
                    image,
                    scaled_template,
                    cv2.TM_CCOEFF_NORMED
                )

                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                if max_val > best_score:
                    best_score = max_val
                    best_location = max_loc
                    best_scale = scale

            except cv2.error:
                # תבנית גדולה מדי או בעיה אחרת
                continue

        return best_score, best_location, best_scale

    @lru_cache(maxsize=100)
    def _cached_template_match(
        self,
        image_hash: int,
        template_hash: int,
        scale: float
    ):
        """
        Template matching עם caching
        (לשימוש עתידי לאופטימיזציה)
        """
        pass

    def visualize_detection(
        self,
        image: np.ndarray,
        result: ArrowResult
    ) -> np.ndarray:
        """
        יצירת ויזואליזציה של הזיהוי (לדיבוג)

        Args:
            image: תמונת המשבצת
            result: תוצאת הזיהוי

        Returns:
            תמונה עם סימון החץ שנמצא
        """
        vis = image.copy()

        if result.direction != 'none':
            # סימון המיקום שבו נמצא החץ
            x, y = result.match_location
            color = (0, 255, 0) if result.confidence > 0.8 else (0, 165, 255)

            cv2.circle(vis, (x, y), 5, color, -1)
            cv2.putText(
                vis,
                f"{result.direction[:10]}",
                (x + 10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1
            )
            cv2.putText(
                vis,
                f"{result.confidence:.2f}",
                (x + 10, y + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1
            )

        return vis

    def get_arrow_icon(self, arrow_direction: str) -> str:
        """
        המרת כיוון חץ לאייקון (לתצוגה ב-UI)

        Args:
            arrow_direction: שם הכיוון

        Returns:
            emoji string
        """
        mapping = {
            "straight-left": "⬅️",
            "straight-right": "➡️",
            "straight-down": "⬇️",
            "straight-up": "⬆️",
            "start-up-turn-right": "⬆️➡️",
            "start-up-turn-left": "⬆️⬅️",
            "start-down-turn-right": "⬇️➡️",
            "start-down-turn-left": "⬇️⬅️",
            "start-left-turn-down": "⬅️⬇️",
            "start-left-turn-up": "⬅️⬆️",
            "start-right-turn-down": "➡️⬇️",
            "start-right-turn-up": "➡️⬆️",
            "none": "❓"
        }
        return mapping.get(arrow_direction, "❓")
