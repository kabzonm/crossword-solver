"""
Split Cell Analyzer
ניתוח משבצות חצויות (עם 2 הגדרות) באמצעות Gemini 3 Pro Vision
"""

import json
import base64
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import cv2

from config.cloud_config import GeminiVisionConfig, get_cloud_config


@dataclass
class SplitDefinition:
    """הגדרה בודדת במשבצת חצויה"""
    text: str
    arrow_direction: str
    position: str  # "top" / "bottom" / "left" / "right"
    confidence: float = 0.0


@dataclass
class SplitCellResult:
    """תוצאת ניתוח משבצת חצויה"""
    definitions: List[SplitDefinition]
    split_type: str  # "horizontal" / "vertical"
    processing_time: float = 0.0
    error: Optional[str] = None


class SplitCellAnalyzer:
    """
    מנתח משבצות חצויות באמצעות Gemini 3 Pro Vision.

    כאשר מזהים 2 חצים במשבצת, קוראים לשירות זה כדי:
    1. לפצל את הטקסט בין 2 ההגדרות
    2. לשייך כל חץ להגדרה המתאימה
    """

    SPLIT_ANALYSIS_PROMPT = """You are analyzing a SPLIT crossword clue cell that contains TWO separate definitions.

Context:
- This is a Hebrew crossword puzzle cell
- The cell is divided and contains 2 different clue definitions
- Each definition has its own arrow pointing to where its answer goes
- Hebrew text reads RIGHT to LEFT

Information provided:
- Full OCR text detected: "{ocr_text}"
- Arrows detected: {arrows_info}

Your task:
1. Look at the image and identify how the cell is split (horizontally or vertically)
2. Identify which text belongs to which definition
3. Match each arrow to its corresponding definition based on position

IMPORTANT:
- The arrow's position (top-right, bottom-left, etc.) indicates which definition it belongs to
- If split horizontally: top arrow → top definition, bottom arrow → bottom definition
- If split vertically: right arrow → right definition, left arrow → left definition

=== MANDATORY VERIFICATION PROCESS ===

You MUST follow this 3-step process:

**STEP 1: Initial Detection**
Look at the image and identify:
- Is there a dividing line? Horizontal or vertical?
- What text is in each section?
- Which arrow belongs to which section?

**STEP 2: Self-Check (REQUIRED)**
Before writing your answer, look at the image AGAIN and verify:
- Look at the dividing line: is it horizontal (splitting top/bottom) or vertical (splitting left/right)?
- Read the text in each section carefully
- Confirm each arrow is matched to its correct definition

**STEP 3: Confirmation**
Compare your Step 1 answer with Step 2. If they match, proceed. If not, use Step 2 results.

=== RESPONSE FORMAT ===

Your response must be ONLY a JSON object (no other text):

{{
  "split_type": "horizontal" or "vertical",
  "definitions": [
    {{
      "text": "text of first definition in Hebrew",
      "arrow_direction": "direction of its arrow (e.g., down, right, left, up)",
      "position": "top" or "bottom" or "left" or "right",
      "confidence": 0.0 to 1.0
    }},
    {{
      "text": "text of second definition in Hebrew",
      "arrow_direction": "direction of its arrow",
      "position": "top" or "bottom" or "left" or "right",
      "confidence": 0.0 to 1.0
    }}
  ]
}}
"""

    def __init__(self, config: GeminiVisionConfig = None):
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
            print("[OK] Gemini 3 Pro Vision client initialized for Split Cell Analyzer")

        except ImportError:
            raise ImportError(
                "google-genai not installed. Run:\n"
                "pip install google-genai"
            )

    def analyze_split_cell(
        self,
        cell_image: np.ndarray,
        ocr_text: str,
        arrows: List[Dict]
    ) -> SplitCellResult:
        """
        מנתח משבצת חצויה ומחזיר את 2 ההגדרות.

        Args:
            cell_image: תמונת המשבצת
            ocr_text: הטקסט שזוהה ע"י OCR
            arrows: רשימת החצים שזוהו [{direction, position, confidence}, ...]

        Returns:
            SplitCellResult עם 2 ההגדרות
        """
        self._initialize_client()

        if not self._client:
            return SplitCellResult(
                definitions=[],
                split_type="unknown",
                error="Gemini client not available"
            )

        if len(arrows) < 2:
            return SplitCellResult(
                definitions=[],
                split_type="unknown",
                error="Less than 2 arrows detected"
            )

        start_time = time.time()

        try:
            # המרת תמונה ל-base64
            image_base64 = self._image_to_base64(cell_image)

            # פורמט מידע על החצים
            arrows_info = ", ".join([
                f"{a.get('direction', 'unknown')} at {a.get('position', 'unknown')}"
                for a in arrows
            ])

            # בניית הפרומפט
            prompt = self.SPLIT_ANALYSIS_PROMPT.format(
                ocr_text=ocr_text,
                arrows_info=arrows_info
            )

            # קריאה ל-Gemini API
            response_text = self._call_gemini_api(image_base64, prompt)

            # פענוח התשובה
            result = self._parse_response(response_text)
            result.processing_time = time.time() - start_time

            return result

        except Exception as e:
            import traceback
            print(f"    [SplitAnalyzer] ERROR: {e}")
            traceback.print_exc()
            return SplitCellResult(
                definitions=[],
                split_type="unknown",
                processing_time=time.time() - start_time,
                error=str(e)
            )

    def _call_gemini_api(self, image_base64: str, prompt: str) -> str:
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
                        prompt
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
                            print(f"    [SplitAnalyzer] Found {len(parts)} parts in response")

                            # עבור על כל ה-parts וזהה thinking vs response
                            for i, part in enumerate(parts):
                                part_text = getattr(part, 'text', None)
                                if part_text:
                                    # בדיקה אם זה part של thinking
                                    if i == 0 and len(parts) > 1:
                                        # Part ראשון כשיש יותר מאחד = thinking
                                        thinking_text = part_text
                                        print(f"    [SplitAnalyzer] === THINKING (part {i}) ===")
                                        print(f"    {thinking_text}")
                                        print(f"    [SplitAnalyzer] === END THINKING ===")
                                    elif i == len(parts) - 1:
                                        # Part אחרון = response (JSON)
                                        response_text = part_text
                                    else:
                                        # Parts באמצע - גם הם thinking
                                        if thinking_text:
                                            thinking_text += "\n" + part_text
                                        else:
                                            thinking_text = part_text
                                        print(f"    [SplitAnalyzer] === THINKING (part {i}) ===")
                                        print(f"    {part_text}")
                                        print(f"    [SplitAnalyzer] === END THINKING ===")

                            # אם יש רק part אחד, זה גם ה-thinking וגם ה-response
                            if len(parts) == 1 and parts[0].text:
                                response_text = parts[0].text
                                # בדיקה אם יש thinking בתוך הטקסט (לפני ה-JSON)
                                if '{' in response_text:
                                    json_start = response_text.find('{')
                                    if json_start > 0:
                                        thinking_text = response_text[:json_start].strip()
                                        if thinking_text:
                                            print(f"    [SplitAnalyzer] === THINKING (embedded) ===")
                                            print(f"    {thinking_text}")
                                            print(f"    [SplitAnalyzer] === END THINKING ===")

                # Fallback ל-response.text אם לא מצאנו parts
                if not response_text and hasattr(response, 'text') and response.text:
                    response_text = response.text
                    # בדיקה אם יש thinking בתוך הטקסט
                    if '{' in response_text:
                        json_start = response_text.find('{')
                        if json_start > 0:
                            thinking_text = response_text[:json_start].strip()
                            if thinking_text:
                                print(f"    [SplitAnalyzer] === THINKING (from text) ===")
                                print(f"    {thinking_text}")
                                print(f"    [SplitAnalyzer] === END THINKING ===")

                if not response_text:
                    print(f"    [SplitAnalyzer] Response object: {response}")
                    raise ValueError(f"Gemini returned empty response")

                print(f"    [SplitAnalyzer] === FULL RESPONSE ===")
                print(f"    {response_text}")
                print(f"    [SplitAnalyzer] === END RESPONSE ===")

                return response_text

            except Exception as e:
                print(f"    [SplitAnalyzer] API attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise e
                time.sleep(self.config.retry_delay * (attempt + 1))

    def _image_to_base64(self, image: np.ndarray) -> str:
        """המרת תמונה ל-base64"""
        # וידוא שהתמונה ב-BGR
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

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

        # קידוד ל-PNG
        _, buffer = cv2.imencode('.png', image)
        return base64.b64encode(buffer).decode('utf-8')

    def _parse_response(self, response_text: str) -> SplitCellResult:
        """פענוח תשובת Gemini"""
        try:
            # ניסיון לחלץ JSON מהתשובה
            json_str = response_text

            # אם יש טקסט לפני/אחרי ה-JSON
            if '{' in json_str:
                start = json_str.find('{')
                end = json_str.rfind('}') + 1
                json_str = json_str[start:end]

            data = json.loads(json_str)

            definitions = []
            for def_data in data.get('definitions', []):
                definitions.append(SplitDefinition(
                    text=def_data.get('text', ''),
                    arrow_direction=def_data.get('arrow_direction', 'unknown'),
                    position=def_data.get('position', 'unknown'),
                    confidence=def_data.get('confidence', 0.5)
                ))

            return SplitCellResult(
                definitions=definitions,
                split_type=data.get('split_type', 'unknown')
            )

        except json.JSONDecodeError as e:
            return SplitCellResult(
                definitions=[],
                split_type="unknown",
                error=f"JSON parse error: {e}"
            )

    def should_analyze(self, arrows: List[Dict]) -> bool:
        """
        בודק אם צריך לנתח את המשבצת כחצויה.
        מחזיר True אם יש בדיוק 2 חצים.
        """
        return len(arrows) == 2

    def fallback_split(
        self,
        ocr_text: str,
        arrows: List[Dict]
    ) -> SplitCellResult:
        """
        פיצול fallback כאשר Gemini לא זמין.
        מחלק את הטקסט שווה בשווה ומשייך לפי מיקום החץ.
        """
        if len(arrows) < 2:
            return SplitCellResult(
                definitions=[],
                split_type="unknown",
                error="Not enough arrows"
            )

        # ניסיון לפצל לפי שורות או מילים
        lines = ocr_text.strip().split('\n')

        if len(lines) >= 2:
            # יש שורות נפרדות
            text1 = lines[0].strip()
            text2 = ' '.join(lines[1:]).strip()
            split_type = "horizontal"
        else:
            # פיצול באמצע
            words = ocr_text.split()
            mid = len(words) // 2
            text1 = ' '.join(words[:mid]) if mid > 0 else ocr_text[:len(ocr_text)//2]
            text2 = ' '.join(words[mid:]) if mid > 0 else ocr_text[len(ocr_text)//2:]
            split_type = "horizontal"  # ברירת מחדל

        # שיוך חצים לפי מיקום
        arrow1 = arrows[0]
        arrow2 = arrows[1]

        # קביעת מיקום לפי position של החץ
        pos1 = arrow1.get('position', 'top')
        pos2 = arrow2.get('position', 'bottom')

        definitions = [
            SplitDefinition(
                text=text1,
                arrow_direction=arrow1.get('direction', 'unknown'),
                position=pos1 if 'top' in pos1 or 'right' in pos1 else 'top',
                confidence=0.3  # ביטחון נמוך ב-fallback
            ),
            SplitDefinition(
                text=text2,
                arrow_direction=arrow2.get('direction', 'unknown'),
                position=pos2 if 'bottom' in pos2 or 'left' in pos2 else 'bottom',
                confidence=0.3
            )
        ]

        return SplitCellResult(
            definitions=definitions,
            split_type=split_type
        )
