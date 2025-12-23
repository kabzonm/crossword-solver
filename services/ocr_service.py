import cv2
import numpy as np
import base64
import streamlit as st
import json
from openai import OpenAI
from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Literal
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.grid import GridMatrix, CellType

# --- סכימות ---
class ZoneLocation(str, Enum):
    UPPER_PART = "upper_part"
    LOWER_PART = "lower_part"
    FULL_CELL = "full_cell"

class ArrowPath(str, Enum):
    STRAIGHT_LEFT = "straight-left"
    STRAIGHT_RIGHT = "straight-right"
    STRAIGHT_DOWN = "straight-down"
    STRAIGHT_UP = "straight-up"
    START_UP_TURN_RIGHT = "start-up-turn-right"
    START_UP_TURN_LEFT = "start-up-turn-left"
    START_DOWN_TURN_RIGHT = "start-down-turn-right"
    START_DOWN_TURN_LEFT = "start-down-turn-left"
    START_LEFT_TURN_DOWN = "start-left-turn-down"
    START_LEFT_TURN_UP = "start-left-turn-up"
    START_RIGHT_TURN_DOWN = "start-right-turn-down"
    START_RIGHT_TURN_UP = "start-right-turn-up"

class ClueItem(BaseModel):
    text: str = Field(description="The Hebrew text found in this zone")
    path: ArrowPath = Field(description="The arrow originating from this zone")
    zone: ZoneLocation = Field(description="Location relative to the red horizontal line")

class CellAnalysis(BaseModel):
    clues: List[ClueItem]
    reasoning: str = Field(description="Explain how you used the Split-Screen: Clean side for text, Marked side for zones.")

class OcrService:
    def __init__(self):
        self.api_key = "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" # <--- המפתח שלך
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            st.error(f"שגיאת אתחול: {e}")

    def recognize_clues(self, original_image: np.ndarray, grid: GridMatrix):
        tasks = []
        h, w, _ = original_image.shape
        padding = 50 

        for r in range(grid.rows):
            for c in range(grid.cols):
                cell = grid.matrix[r][c]
                if hasattr(cell, 'error'): del cell.error
                cell.parsed_clues = []
                
                if cell.type == CellType.CLUE:
                    if hasattr(cell, 'bbox') and cell.bbox:
                        x1, y1, x2, y2 = cell.bbox
                        
                        # חיתוך רחב
                        px1 = max(0, x1 - padding)
                        py1 = max(0, y1 - padding)
                        px2 = min(w, x2 + padding)
                        py2 = min(h, y2 + padding)
                        
                        raw_roi = original_image[py1:py2, px1:px2].copy()
                        
                        rel_x1 = x1 - px1
                        rel_y1 = y1 - py1
                        rel_x2 = x2 - px1
                        rel_y2 = y2 - py1

                        # 1. יצירת גרסה נקייה (Clean) - לקריאת טקסט
                        # מפעילים רק חידוד, בלי קשקושים
                        clean_roi = self._preprocess_image(raw_roi)
                        
                        # 2. יצירת גרסה מסומנת (Marked) - להבנת מיקום
                        marked_roi = clean_roi.copy()
                        center_y = rel_y1 + (rel_y2 - rel_y1) // 2
                        
                        # מסגרת כחולה
                        cv2.rectangle(marked_roi, (rel_x1, rel_y1), (rel_x2, rel_y2), (255, 0, 0), 2)
                        # קו אדום חוצה
                        cv2.line(marked_roi, (rel_x1, center_y), (rel_x2, center_y), (0, 0, 255), 2)
                        
                        # 3. איחוד התמונות: נקי משמאל, מסומן מימין (עם רווח לבן קטן)
                        spacer = np.full((clean_roi.shape[0], 10, 3), 255, dtype=np.uint8) # פס לבן מפריד
                        combined_img = np.hstack([clean_roi, spacer, marked_roi])

                        # שמירה
                        _, buffer = cv2.imencode('.png', combined_img)
                        b64_img = base64.b64encode(buffer).decode('utf-8')
                        
                        # נשמור את התמונה המאוחדת כדי שתראה אותה בטבלה
                        cell.debug_image = f"data:image/png;base64,{b64_img}"
                        
                        tasks.append({"roi": combined_img, "row": r, "col": c})

        if not tasks:
            st.warning("לא נמצאו הגדרות.")
            return grid

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_cell = {
                executor.submit(self._process_split_screen_cell, task["roi"]): task 
                for task in tasks
            }

            for i, future in enumerate(as_completed(future_to_cell)):
                task = future_to_cell[future]
                r, c = task["row"], task["col"]
                
                try:
                    result = future.result()
                    if result:
                        clues_dicts = []
                        zones_found = []
                        
                        for item in result.clues:
                            clues_dicts.append({
                                "text": item.text,
                                "path": item.path.value,
                                "zone": item.zone.value
                            })
                            zones_found.append(item.zone.value)
                        
                        grid.matrix[r][c].parsed_clues = clues_dicts
                        
                        if "upper_part" in zones_found and "lower_part" in zones_found:
                            grid.matrix[r][c].solution = "SPLIT"
                        elif len(zones_found) == 1:
                            grid.matrix[r][c].solution = "SINGLE"
                        else:
                            grid.matrix[r][c].solution = f"Found: {len(zones_found)}"
                            
                    else:
                        grid.matrix[r][c].solution = "Failed"
                except Exception as e:
                    grid.matrix[r][c].error = str(e)
                
                progress_bar.progress((i + 1) / len(tasks))
                status_text.text(f"מעבד: {i+1}/{len(tasks)}")

        status_text.empty()
        progress_bar.empty()
        return grid

    def _preprocess_image(self, image):
        # שיפור קונטרסט וחדות
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        final = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        return final

    def _process_split_screen_cell(self, image_roi):
        _, buffer = cv2.imencode('.jpg', image_roi)
        base64_image = base64.b64encode(buffer).decode('utf-8')

        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "You are a crossword digitizer utilizing a Split-Screen view."},
                    {"role": "user", "content": [
                        {"type": "text", "text": """
You are provided with a SPLIT-SCREEN image of the same cell:
1. **LEFT SIDE (Clean)**: Use this side ONLY for reading the Hebrew text. It has no obstructions.
2. **RIGHT SIDE (Marked)**: Use this side ONLY for determining spatial location (Upper/Lower). It has a RED LINE.

**Instructions:**
- Look at the **LEFT** image to read a text.
- Look at the corresponding spot on the **RIGHT** image to see if that text falls ABOVE or BELOW the red line.

**Zones:**
- **UPPER_PART**: Text is distinctly above the red line.
- **LOWER_PART**: Text is distinctly below the red line.
- **FULL_CELL**: Text crosses the line or is centered alone.

**Task:**
- Extract text (from left) and arrow path.
- Map it to the correct zone (using right).
                        """},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]}
                ],
                response_format=CellAnalysis,
                temperature=0.0,
            )
            return response.choices[0].message.parsed
        except Exception as e:
            return None

    def _path_to_icon(self, path):
        mapping = {
            "straight-left": "⬅️", "straight-right": "➡️", "straight-down": "⬇️", "straight-up": "⬆️",
            "start-up-turn-right": "⬆️➡️", "start-up-turn-left": "⬆️⬅️",
            "start-down-turn-right": "⬇️➡️", "start-down-turn-left": "⬇️⬅️",
            "start-left-turn-down": "⬅️⬇️", "start-left-turn-up": "⬅️⬆️",
            "start-right-turn-down": "➡️⬇️", "start-right-turn-up": "➡️⬆️",
        }
        return mapping.get(path, "❓")