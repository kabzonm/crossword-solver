"""
Claude Vision Arrow Detector
זיהוי כיוון חצים באמצעות Claude Vision API
"""

import base64
import time
import json
import re
from typing import Optional, Dict, List, Tuple
import numpy as np
import cv2

from config.cloud_config import ClaudeVisionConfig, get_cloud_config
from models.recognition_result import ArrowResult


class ClaudeArrowDetector:
    """
    זיהוי חצים באמצעות Claude Vision API
    יתרון: הבנת הקשר ויזואלי, זיהוי מדויק של כיוונים מורכבים
    """

    # מיפוי שמות חצים - תואם לשמות הקיימים ב-ArrowConfig
    ARROW_TYPES = {
        # Straight arrows
        "right": "straight-right",
        "left": "straight-left",
        "down": "straight-down",
        "up": "straight-up",
        "straight-right": "straight-right",
        "straight-left": "straight-left",
        "straight-down": "straight-down",
        "straight-up": "straight-up",

        # Step arrows - normalized names
        "up-right": "start-up-turn-right",
        "up-left": "start-up-turn-left",
        "down-right": "start-down-turn-right",
        "down-left": "start-down-turn-left",
        "left-down": "start-left-turn-down",
        "left-up": "start-left-turn-up",
        "right-down": "start-right-turn-down",
        "right-up": "start-right-turn-up",

        # Full names (for completeness)
        "start-up-turn-right": "start-up-turn-right",
        "start-up-turn-left": "start-up-turn-left",
        "start-down-turn-right": "start-down-turn-right",
        "start-down-turn-left": "start-down-turn-left",
        "start-left-turn-down": "start-left-turn-down",
        "start-left-turn-up": "start-left-turn-up",
        "start-right-turn-down": "start-right-turn-down",
        "start-right-turn-up": "start-right-turn-up",

        # No arrow
        "none": "none",
        "no_arrow": "none",
        "empty": "none",
    }

    DETECTION_PROMPT = """Analyze this Hebrew crossword clue cell image.

TASK: Detect ALL arrows in the cell. A cell can have 0, 1, or 2 arrows.

IMPORTANT CONTEXT:
- This is a Hebrew crossword where clue cells contain text definitions
- Arrows indicate WHERE to write the answer (offset from this cell)
- A cell may have TWO separate clues, each with its own arrow
- Look carefully at ALL corners and edges of the cell

Arrow types to detect:
1. STRAIGHT arrows (answer starts in adjacent cell):
   - "down": arrow pointing down
   - "up": arrow pointing up
   - "left": arrow pointing left
   - "right": arrow pointing right

2. L-SHAPED arrows (answer starts with offset - goes one direction then turns):
   - "down-right": goes down then turns right
   - "down-left": goes down then turns left
   - "up-right": goes up then turns right
   - "up-left": goes up then turns left
   - "right-down": goes right then turns down
   - "right-up": goes right then turns up
   - "left-down": goes left then turns down
   - "left-up": goes left then turns up

Look carefully for:
- Small triangular arrow heads at cell edges
- L-shaped or bent arrows
- Lines with pointed ends
- Check ALL corners: top-left, top-right, bottom-left, bottom-right

Respond ONLY with JSON:
{
  "arrows": [
    {"direction": "down", "confidence": 0.9, "position": "top-right"},
    {"direction": "right", "confidence": 0.85, "position": "bottom-left"}
  ]
}

If only ONE arrow: {"arrows": [{"direction": "down", "confidence": 0.9, "position": "center"}]}
If NO arrows: {"arrows": []}
"""

    def __init__(self, config: ClaudeVisionConfig = None):
        """
        Args:
            config: הגדרות Claude Vision (אם None, לוקח מ-cloud_config)
        """
        self.config = config or get_cloud_config().claude
        self._client = None
        self._initialized = False

    def _initialize_client(self) -> None:
        """אתחול הלקוח של Anthropic"""
        if self._initialized:
            return

        try:
            import anthropic

            if not self.config.api_key:
                raise ValueError(
                    "Claude Vision requires ANTHROPIC_API_KEY environment variable"
                )

            self._client = anthropic.Anthropic(api_key=self.config.api_key)
            self._initialized = True
            print("[OK] Claude Vision client initialized")

        except ImportError:
            raise ImportError(
                "anthropic not installed. Run:\n"
                "pip install anthropic"
            )

    def detect_arrow(
        self,
        cell_image: np.ndarray,
        cell_bbox: Tuple[int, int, int, int] = None
    ) -> List[ArrowResult]:
        """
        זיהוי חצים במשבצת (עד 2 חצים)

        Args:
            cell_image: תמונת המשבצת (BGR numpy array)
            cell_bbox: קואורדינטות המשבצת (לא בשימוש כרגע)

        Returns:
            List[ArrowResult] - רשימת חצים שזוהו (0-2)
        """
        self._initialize_client()
        start_time = time.time()

        try:
            # המרה ל-base64
            image_base64 = self._image_to_base64(cell_image)
            print(f"    [Claude] Image converted to base64 (len={len(image_base64)})")

            # קריאה ל-API
            response = self._call_claude_api(image_base64)
            print(f"    [Claude] API response: {response[:150]}...")

            # פענוח התשובה - מחזירה רשימה
            results = self._parse_response(response)
            processing_time = time.time() - start_time

            for result in results:
                result.processing_time = processing_time

            print(f"    [Claude] Parsed: {len(results)} arrows found")
            for i, r in enumerate(results):
                print(f"      Arrow {i+1}: direction={r.direction}, confidence={r.confidence}, position={r.position}")

            return results

        except Exception as e:
            import traceback
            print(f"    [Claude] ERROR: {e}")
            traceback.print_exc()
            return [ArrowResult(
                direction="none",
                confidence=0.0,
                processing_time=time.time() - start_time,
                template_matched=f"error: {str(e)}"
            )]

    def _call_claude_api(self, image_base64: str) -> str:
        """קריאה ל-Claude Vision API"""
        for attempt in range(self.config.max_retries):
            try:
                message = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": image_base64
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": self.DETECTION_PROMPT
                                }
                            ]
                        }
                    ]
                )

                return message.content[0].text

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise e
                time.sleep(self.config.retry_delay * (attempt + 1))

    def _parse_response(self, response_text: str) -> List[ArrowResult]:
        """פענוח תשובת Claude - מחזירה רשימת חצים"""
        try:
            # חיפוש JSON בתשובה (כולל מערכים)
            json_match = re.search(r'\{[^{}]*"arrows"[^{}]*\[.*?\][^{}]*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # ניסיון לפרסר את כל התשובה כ-JSON
                data = json.loads(response_text)

            arrows_data = data.get('arrows', [])

            # אם אין מערך arrows, ננסה פורמט ישן
            if not arrows_data and 'direction' in data:
                arrows_data = [data]

            results = []
            for arrow_data in arrows_data:
                raw_direction = arrow_data.get('direction', 'none').lower().strip()
                direction = self.ARROW_TYPES.get(raw_direction, raw_direction)

                # אם הכיוון לא מוכר, החזר none
                if direction not in self.ARROW_TYPES.values():
                    direction = 'none'

                confidence = float(arrow_data.get('confidence', 0.5))
                position = arrow_data.get('position', 'unknown')

                results.append(ArrowResult(
                    direction=direction,
                    confidence=confidence,
                    position=position,
                    match_location=(0, 0),
                    scale_used=1.0,
                    template_matched=f"claude: {arrow_data.get('description', '')}"
                ))

            # אם לא נמצאו חצים, החזר רשימה עם "none"
            if not results:
                results.append(ArrowResult(
                    direction="none",
                    confidence=0.5,
                    position="unknown",
                    template_matched="claude: no arrows found"
                ))

            return results

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # אם לא הצלחנו לפרסר, ננסה להבין מהטקסט
            return [self._parse_text_response(response_text)]

    def _parse_text_response(self, text: str) -> ArrowResult:
        """ניסיון לפענח תשובה לא-JSON"""
        text_lower = text.lower()

        # חיפוש מילות מפתח
        for keyword, direction in self.ARROW_TYPES.items():
            if keyword in text_lower:
                return ArrowResult(
                    direction=direction,
                    confidence=0.6,  # confidence נמוך יותר כי לא היה JSON
                    template_matched=f"claude_text_parse: {text[:100]}"
                )

        return ArrowResult(
            direction="none",
            confidence=0.3,
            template_matched=f"claude_parse_failed: {text[:100]}"
        )

    def _image_to_base64(self, image: np.ndarray) -> str:
        """המרת תמונה ל-base64"""
        # Ensure minimum size for Claude to see details properly
        h, w = image.shape[:2]
        min_size = 150  # Claude needs reasonable resolution

        if h < min_size or w < min_size:
            scale = max(min_size / h, min_size / w, 3.0)
            image = cv2.resize(image, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_CUBIC)

        # Add white border to help Claude see edges
        border = 10
        image = cv2.copyMakeBorder(image, border, border, border, border,
                                   cv2.BORDER_CONSTANT, value=[255, 255, 255])

        # המרה ל-PNG ואז ל-base64
        _, buffer = cv2.imencode('.png', image)
        return base64.b64encode(buffer).decode('utf-8')

    def batch_detect(self, images: List[np.ndarray]) -> List[List[ArrowResult]]:
        """
        זיהוי batch של תמונות

        Args:
            images: רשימת תמונות

        Returns:
            רשימת רשימות ArrowResult (כל תמונה יכולה להחזיר מספר חצים)
        """
        results = []
        for image in images:
            result = self.detect_arrow(image)
            results.append(result)
        return results

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
            "start-up-turn-right": "↗️",
            "start-up-turn-left": "↖️",
            "start-down-turn-right": "↘️",
            "start-down-turn-left": "↙️",
            "start-left-turn-down": "↙️",
            "start-left-turn-up": "↖️",
            "start-right-turn-down": "↘️",
            "start-right-turn-up": "↗️",
            "none": "❓"
        }
        return mapping.get(arrow_direction, "❓")
