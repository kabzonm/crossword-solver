"""
Gemini 3 Pro Vision Arrow Detector
זיהוי כיוון חצים באמצעות Google Gemini 3 Pro Vision API
"""

import base64
import time
import json
import re
from typing import Optional, Dict, List, Tuple
import numpy as np
import cv2

from config.cloud_config import GeminiVisionConfig, get_cloud_config
from models.recognition_result import ArrowResult, ArrowDetectionResult


class GeminiArrowDetector:
    """
    זיהוי חצים באמצעות Gemini 3 Pro Vision API
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

    DETECTION_PROMPT = """You are analyzing a Hebrew crossword puzzle clue cell.

TASK: Detect ALL arrows that ORIGINATE FROM the center cell (the main cell with text).

=== CRITICAL: ARROWS FROM NEIGHBORING CELLS ===
The image shows the main cell (center) with a small surrounding area.
- ONLY detect arrows that START from inside the main center cell
- If you see an arrow at the edge that might be from a neighbor cell, mark it with "outside_cell": true
- These outside arrows will be filtered out later

=== SPLIT CELLS - IMPORTANT! ===
Some cells are SPLIT CELLS containing TWO separate clues with TWO arrows!

Signs of a split cell:
- A dividing line inside the cell (horizontal or vertical gray/black line)
- Two separate text areas within the cell
- Two arrows pointing in different directions

If you see ANY sign of a split cell, set "is_split_cell": true and make sure to detect BOTH arrows!

=== WHAT TO DETECT - TWO SEPARATE QUESTIONS ===

**CRITICAL: These are TWO DIFFERENT things!**

1. **exit_side**: From which EDGE of the cell does the arrow's LINE cross the cell border?
   - This is WHERE the arrow leaves the cell
   - Values: "top", "bottom", "left", "right"
   - Example: If the arrow line crosses the bottom border of the cell → exit_side="bottom"

2. **arrowhead_direction**: Which direction does the TRIANGULAR ARROWHEAD (▼ ▲ ◀ ▶) point?
   - This is WHERE the pointy tip is aiming
   - Values: "up", "down", "left", "right"
   - Example: If the arrowhead looks like ▼ (pointing downward) → arrowhead_direction="down"
   - Example: If the arrowhead looks like ▶ (pointing right) → arrowhead_direction="right"

**IMPORTANT DISTINCTION:**
- For a STRAIGHT arrow: exit_side and arrowhead_direction are the SAME
  (arrow exits bottom and points down → exit_side="bottom", arrowhead_direction="down")
- For an L-SHAPED arrow: exit_side and arrowhead_direction are DIFFERENT
  (arrow exits right side but then turns and points down → exit_side="right", arrowhead_direction="down")

3. **position_in_side** (for split cells): Where along that side is the arrow?
   - Values: "start", "middle", "end"

4. **outside_cell** (optional): Set to true if the arrow might be from a neighboring cell

=== EXAMPLES ===

STRAIGHT arrow pointing down:
```
+-------+
|  clue |
|   |   |
+---|---+
    v
```
exit_side="bottom", arrowhead_direction="down"

L-SHAPED arrow (exits right, points down):
```
+-------+
|  clue |---+
+-------+   |
            v
```
exit_side="right", arrowhead_direction="down"

SPLIT CELL with 2 arrows:
```
+-------+
| clue1 |-->
|-------|
| clue2 |
+---|---+
    v
```
is_split_cell=true, two arrows: one exits right, one exits bottom

=== MANDATORY VERIFICATION PROCESS ===

You MUST follow this 3-step process:

**STEP 1: Initial Detection**
Look at the image and identify:
- How many arrows do you see coming FROM the center cell?
- For each arrow: which edge does it exit from? where does the arrowhead point?

**STEP 2: Self-Check (REQUIRED)**
Before writing your answer, look at the image AGAIN and verify:
- Look at the TOP edge: is there an arrow exiting there? If yes, where does its arrowhead point?
- Look at the BOTTOM edge: is there an arrow exiting there? If yes, where does its arrowhead point?
- Look at the LEFT edge: is there an arrow exiting there? If yes, where does its arrowhead point?
- Look at the RIGHT edge: is there an arrow exiting there? If yes, where does its arrowhead point?

**STEP 3: Confirmation**
Compare your Step 1 answer with Step 2. If they match, proceed. If not, use Step 2 results.

=== RESPONSE FORMAT ===

Your response must be ONLY a JSON object (no other text):

{"is_split_cell": false, "arrows": [{"exit_side": "bottom", "arrowhead_direction": "down", "confidence": 0.95}]}

**RULES:**
- exit_side MUST be one of: "top", "bottom", "left", "right"
- arrowhead_direction MUST be one of: "up", "down", "left", "right"
- If you cannot determine exit_side or arrowhead_direction, you did not complete the verification process correctly
- NEVER return an arrow without BOTH exit_side AND arrowhead_direction
- If truly no arrows exist, return: {"is_split_cell": false, "arrows": []}
"""

    def __init__(self, config: 'GeminiVisionConfig' = None):
        """
        Args:
            config: הגדרות Gemini Vision (אם None, לוקח מ-cloud_config)
        """
        self.config = config or get_cloud_config().gemini
        self._client = None
        self._initialized = False

    def _initialize_client(self) -> None:
        """אתחול הלקוח של Google GenAI"""
        if self._initialized:
            return

        try:
            from google import genai

            if not self.config.api_key:
                raise ValueError(
                    "Gemini Vision requires GOOGLE_API_KEY environment variable or google_vision_api.txt file"
                )

            self._client = genai.Client(api_key=self.config.api_key)
            self._initialized = True
            print("[OK] Gemini 3 Pro Vision client initialized")

        except ImportError:
            raise ImportError(
                "google-genai not installed. Run:\n"
                "pip install google-genai"
            )

    def detect_arrow(
        self,
        cell_image: np.ndarray,
        cell_bbox: Tuple[int, int, int, int] = None
    ) -> ArrowDetectionResult:
        """
        זיהוי חצים במשבצת (עד 2 חצים)

        Args:
            cell_image: תמונת המשבצת (BGR numpy array)
            cell_bbox: קואורדינטות המשבצת (לא בשימוש כרגע)

        Returns:
            ArrowDetectionResult - תוצאת הזיהוי כולל is_split_cell
        """
        self._initialize_client()
        start_time = time.time()

        try:
            # המרה ל-base64
            image_base64 = self._image_to_base64(cell_image)
            print(f"    [Gemini] Image converted to base64 (len={len(image_base64)})")

            # קריאה ל-API
            response = self._call_gemini_api(image_base64)
            print(f"    [Gemini] === FULL API RESPONSE ===")
            print(f"    {response}")
            print(f"    [Gemini] === END RESPONSE ===")

            # פענוח התשובה - מחזירה ArrowDetectionResult
            detection_result = self._parse_response(response)
            processing_time = time.time() - start_time
            detection_result.processing_time = processing_time

            for arrow in detection_result.arrows:
                arrow.processing_time = processing_time

            print(f"    [Gemini] Parsed: {len(detection_result.arrows)} arrows found, is_split_cell={detection_result.is_split_cell}")
            for i, r in enumerate(detection_result.arrows):
                print(f"      Arrow {i+1}: direction={r.direction}, confidence={r.confidence}, position={r.position}")

            return detection_result

        except Exception as e:
            import traceback
            print(f"    [Gemini] ERROR: {e}")
            traceback.print_exc()
            return ArrowDetectionResult(
                arrows=[ArrowResult(
                    direction="none",
                    confidence=0.0,
                    processing_time=time.time() - start_time,
                    template_matched=f"error: {str(e)}"
                )],
                is_split_cell=False,
                processing_time=time.time() - start_time
            )

    def _call_gemini_api(self, image_base64: str) -> str:
        """קריאה ל-Gemini 3 Pro Vision API"""
        from google.genai import types

        for attempt in range(self.config.max_retries):
            try:
                # יצירת Part מ-bytes
                image_bytes = base64.b64decode(image_base64)
                image_part = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/png"
                )

                # הגדרת thinking budget כדי להגביל את כמות הטוקנים לחשיבה
                thinking_config = None
                if hasattr(self.config, 'thinking_budget') and self.config.thinking_budget:
                    thinking_config = types.ThinkingConfig(
                        thinking_budget=self.config.thinking_budget
                    )

                response = self._client.models.generate_content(
                    model=self.config.model,
                    contents=[
                        image_part,
                        self.DETECTION_PROMPT
                    ],
                    config=types.GenerateContentConfig(
                        temperature=self.config.temperature,
                        max_output_tokens=self.config.max_tokens,
                        thinking_config=thinking_config,
                    )
                )

                # בדיקה שהתגובה תקינה
                if response is None:
                    raise ValueError("Gemini returned None response")

                # חילוץ כל ה-parts מהתשובה
                thinking_text = None
                response_text = None

                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                            parts = candidate.content.parts
                            print(f"    [Gemini] Found {len(parts)} parts in response")

                            # עבור על כל ה-parts וזהה thinking vs response
                            for i, part in enumerate(parts):
                                part_text = getattr(part, 'text', None)
                                if part_text:
                                    # בדיקה אם זה part של thinking
                                    # Gemini 3 Pro מחזיר thinking ב-part נפרד לפני ה-response
                                    if i == 0 and len(parts) > 1:
                                        # Part ראשון כשיש יותר מאחד = thinking
                                        thinking_text = part_text
                                        print(f"    [Gemini] === THINKING (part {i}) ===")
                                        print(f"    {thinking_text}")
                                        print(f"    [Gemini] === END THINKING ===")
                                    elif i == len(parts) - 1:
                                        # Part אחרון = response (JSON)
                                        response_text = part_text
                                    else:
                                        # Parts באמצע - גם הם thinking
                                        if thinking_text:
                                            thinking_text += "\n" + part_text
                                        else:
                                            thinking_text = part_text
                                        print(f"    [Gemini] === THINKING (part {i}) ===")
                                        print(f"    {part_text}")
                                        print(f"    [Gemini] === END THINKING ===")

                            # אם יש רק part אחד, זה גם ה-thinking וגם ה-response
                            if len(parts) == 1 and parts[0].text:
                                response_text = parts[0].text
                                # בדיקה אם יש thinking בתוך הטקסט (לפני ה-JSON)
                                if '{' in response_text:
                                    json_start = response_text.find('{')
                                    if json_start > 0:
                                        thinking_text = response_text[:json_start].strip()
                                        if thinking_text:
                                            print(f"    [Gemini] === THINKING (embedded) ===")
                                            print(f"    {thinking_text}")
                                            print(f"    [Gemini] === END THINKING ===")

                # Fallback ל-response.text אם לא מצאנו parts
                if not response_text and hasattr(response, 'text') and response.text:
                    response_text = response.text
                    # בדיקה אם יש thinking בתוך הטקסט
                    if '{' in response_text:
                        json_start = response_text.find('{')
                        if json_start > 0:
                            thinking_text = response_text[:json_start].strip()
                            if thinking_text:
                                print(f"    [Gemini] === THINKING (from text) ===")
                                print(f"    {thinking_text}")
                                print(f"    [Gemini] === END THINKING ===")

                if not response_text:
                    # הדפסת מידע debug
                    print(f"    [Gemini] Response object: {response}")
                    print(f"    [Gemini] Response type: {type(response)}")
                    if hasattr(response, 'candidates'):
                        print(f"    [Gemini] Candidates: {response.candidates}")
                    raise ValueError(f"Gemini returned empty response. Response: {response}")

                return response_text

            except Exception as e:
                print(f"    [Gemini] API attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise e
                time.sleep(self.config.retry_delay * (attempt + 1))

    # מיפוי פאה לכיוון
    SIDE_TO_DIRECTION = {
        'top': 'up',
        'bottom': 'down',
        'left': 'left',
        'right': 'right'
    }

    def _parse_response(self, response_text: str) -> ArrowDetectionResult:
        """פענוח תשובת Gemini - מחזירה ArrowDetectionResult"""
        try:
            # בדיקה שהתשובה לא None
            if response_text is None:
                print(f"      [Parse] Response is None, returning 'none'")
                return ArrowDetectionResult(
                    arrows=[ArrowResult(
                        direction="none",
                        confidence=0.0,
                        template_matched="gemini: null response"
                    )],
                    is_split_cell=False
                )

            # חיפוש JSON בתשובה (כולל מערכים)
            json_match = re.search(r'\{[^{}]*"arrows"[^{}]*\[.*?\][^{}]*\}', response_text, re.DOTALL)
            if json_match:
                print(f"      [Parse] Found JSON with 'arrows' key")
                data = json.loads(json_match.group())
            else:
                # ניסיון לפרסר את כל התשובה כ-JSON
                print(f"      [Parse] No 'arrows' pattern found, trying full JSON parse")
                data = json.loads(response_text)

            print(f"      [Parse] Parsed JSON data: {data}")

            # קריאת is_split_cell
            is_split_cell = data.get('is_split_cell', False)

            arrows_data = data.get('arrows', [])

            # אם אין מערך arrows, ננסה פורמט ישן
            if not arrows_data and ('direction' in data or 'exit_side' in data or 'offset_direction' in data):
                arrows_data = [data]

            results = []
            filtered_count = 0

            for arrow_data in arrows_data:
                print(f"      [Parse] Arrow data: {arrow_data}")

                # סינון חצים מחוץ לגבול או עם exit_side לא ידוע
                if arrow_data.get('outside_cell', False):
                    print(f"      [Filter] Skipping outside_cell arrow: {arrow_data}")
                    filtered_count += 1
                    continue

                exit_side = arrow_data.get('exit_side', '').lower().strip()
                if exit_side == 'unknown':
                    print(f"      [Filter] Skipping unknown exit_side arrow: {arrow_data}")
                    filtered_count += 1
                    continue

                # פורמט חדש: exit_side + arrowhead_direction
                if 'exit_side' in arrow_data and 'arrowhead_direction' in arrow_data:
                    print(f"      [Parse] Using NEW format: exit_side + arrowhead_direction")
                    arrowhead = arrow_data['arrowhead_direction'].lower().strip()
                    position_in_side = arrow_data.get('position_in_side', 'middle')

                    # המרת פאה לכיוון
                    offset_direction = self.SIDE_TO_DIRECTION.get(exit_side, exit_side)
                    writing_direction = arrowhead

                    # חישוב סוג החץ
                    if offset_direction == writing_direction:
                        # חץ ישר
                        direction = self.ARROW_TYPES.get(offset_direction, f"straight-{offset_direction}")
                    else:
                        # חץ L-shaped
                        combined = f"{offset_direction}-{writing_direction}"
                        direction = self.ARROW_TYPES.get(combined, f"start-{offset_direction}-turn-{writing_direction}")

                    confidence = float(arrow_data.get('confidence', 0.85))

                    results.append(ArrowResult(
                        direction=direction,
                        confidence=confidence,
                        position=position_in_side,
                        match_location=(0, 0),
                        scale_used=1.0,
                        template_matched=f"gemini: exit={exit_side}, arrow={arrowhead}, pos={position_in_side}",
                        exit_side=exit_side,
                        arrowhead_direction=arrowhead
                    ))

                # פורמט ישן: offset_direction + writing_direction
                elif 'offset_direction' in arrow_data and 'writing_direction' in arrow_data:
                    print(f"      [Parse] Using OLD format: offset_direction + writing_direction")
                    offset = arrow_data['offset_direction'].lower().strip()
                    writing = arrow_data['writing_direction'].lower().strip()

                    if offset == writing:
                        direction = self.ARROW_TYPES.get(offset, f"straight-{offset}")
                    else:
                        combined = f"{offset}-{writing}"
                        direction = self.ARROW_TYPES.get(combined, f"start-{offset}-turn-{writing}")

                    confidence = float(arrow_data.get('confidence', 0.8))

                    # ננסה לשמור exit_side ו-arrowhead אם קיימים
                    old_exit_side = arrow_data.get('exit_side')
                    old_arrowhead = arrow_data.get('arrowhead_direction')

                    results.append(ArrowResult(
                        direction=direction,
                        confidence=confidence,
                        position=arrow_data.get('position', 'unknown'),
                        match_location=(0, 0),
                        scale_used=1.0,
                        template_matched=f"gemini: offset={offset}, writing={writing}",
                        exit_side=old_exit_side,
                        arrowhead_direction=old_arrowhead
                    ))

                # פורמט ישן ביותר: direction בלבד
                elif 'direction' in arrow_data:
                    print(f"      [Parse] Using OLDEST format: direction only")
                    raw_direction = arrow_data.get('direction', 'none').lower().strip()
                    direction = self.ARROW_TYPES.get(raw_direction, raw_direction)

                    if direction not in self.ARROW_TYPES.values():
                        direction = 'none'

                    confidence = float(arrow_data.get('confidence', 0.5))
                    position = arrow_data.get('position', 'unknown')

                    # ננסה לשמור exit_side ו-arrowhead אם קיימים
                    old_exit_side = arrow_data.get('exit_side')
                    old_arrowhead = arrow_data.get('arrowhead_direction')

                    results.append(ArrowResult(
                        direction=direction,
                        confidence=confidence,
                        position=position,
                        match_location=(0, 0),
                        scale_used=1.0,
                        template_matched=f"gemini: {arrow_data.get('description', '')}",
                        exit_side=old_exit_side,
                        arrowhead_direction=old_arrowhead
                    ))

            if filtered_count > 0:
                print(f"      [Filter] Filtered out {filtered_count} arrows (outside_cell or unknown)")

            # אם לא נמצאו חצים, החזר רשימה עם "none"
            if not results:
                results.append(ArrowResult(
                    direction="none",
                    confidence=0.5,
                    position="unknown",
                    template_matched="gemini: no arrows found"
                ))

            return ArrowDetectionResult(
                arrows=results,
                is_split_cell=is_split_cell
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # אם לא הצלחנו לפרסר, ננסה להבין מהטקסט
            arrow = self._parse_text_response(response_text)
            return ArrowDetectionResult(
                arrows=[arrow],
                is_split_cell=False
            )

    # מיפוי הפוך - מ-direction ל-exit_side ו-arrowhead
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
    }

    def _parse_text_response(self, text: str) -> ArrowResult:
        """ניסיון לפענח תשובה לא-JSON"""
        print(f"      [TextParse] Trying to parse non-JSON response: {text[:200]}...")
        text_lower = text.lower()

        # חיפוש מילות מפתח
        for keyword, direction in self.ARROW_TYPES.items():
            if keyword in text_lower:
                # חישוב exit_side ו-arrowhead מה-direction
                exit_side, arrowhead = self.DIRECTION_TO_RAW.get(direction, (None, None))
                print(f"      [TextParse] Found keyword '{keyword}' -> direction={direction}, exit={exit_side}, arrow={arrowhead}")
                return ArrowResult(
                    direction=direction,
                    confidence=0.6,  # confidence נמוך יותר כי לא היה JSON
                    template_matched=f"gemini_text_parse: {text[:100]}",
                    exit_side=exit_side,
                    arrowhead_direction=arrowhead
                )

        print(f"      [TextParse] No keywords found, returning 'none'")
        return ArrowResult(
            direction="none",
            confidence=0.3,
            template_matched=f"gemini_parse_failed: {text[:100]}"
        )

    def _image_to_base64(self, image: np.ndarray) -> str:
        """המרת תמונה ל-base64"""
        # Ensure minimum size for Gemini to see details properly
        h, w = image.shape[:2]
        min_size = 150

        if h < min_size or w < min_size:
            scale = max(min_size / h, min_size / w, 3.0)
            image = cv2.resize(image, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_CUBIC)

        # Add white border to help Gemini see edges
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
            "straight-left": "<-",
            "straight-right": "->",
            "straight-down": "v",
            "straight-up": "^",
            "start-up-turn-right": "^>",
            "start-up-turn-left": "<^",
            "start-down-turn-right": "v>",
            "start-down-turn-left": "<v",
            "start-left-turn-down": "<v",
            "start-left-turn-up": "<^",
            "start-right-turn-down": ">v",
            "start-right-turn-up": ">^",
            "none": "?"
        }
        return mapping.get(arrow_direction, "?")
