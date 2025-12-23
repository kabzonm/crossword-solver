import cv2
import numpy as np
from PIL import Image
from models.grid import GridMatrix, CellType, SplitType, ClueMeta, Cell

class VisionService:
    def generate_preview(self, pil_image, rect, rows, cols) -> np.ndarray:
        image = np.array(pil_image.convert('RGB'))
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        x, y, w, h = int(rect['left']), int(rect['top']), int(rect['width']), int(rect['height'])
        img_h, img_w = image.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = min(w, img_w - x), min(h, img_h - y)
        cell_w = w / cols
        cell_h = h / rows
        for r in range(rows + 1):
            y_pos = int(y + r * cell_h)
            cv2.line(image, (x, y_pos), (x + w, y_pos), (0, 255, 0), 2)
        for c in range(cols + 1):
            x_pos = int(x + c * cell_w)
            cv2.line(image, (x_pos, y), (x_pos, y + h), (0, 255, 0), 2)
        return image

    def process_lines_grid(self, pil_image, h_lines, v_lines, rows, cols) -> tuple[GridMatrix, np.ndarray, np.ndarray]:
        full_image = np.array(pil_image.convert('RGB'))
        full_image = cv2.cvtColor(full_image, cv2.COLOR_RGB2BGR)
        
        # מיון קווים
        h_lines.sort(key=lambda l: l['y'])
        v_lines.sort(key=lambda l: l['x'])
        
        if len(h_lines) < 2 or len(v_lines) < 2:
            return None, full_image, full_image

        grid_obj = GridMatrix(rows, cols)
        grid_obj.initialize_grid()
        
        preview_img = full_image.copy()

        # לולאה על הקווים האמיתיים שהוגדרו
        for r in range(min(rows, len(h_lines) - 1)):
            for c in range(min(cols, len(v_lines) - 1)):
                y1 = int(h_lines[r]['y'])
                y2 = int(h_lines[r+1]['y'])
                x1 = int(v_lines[c]['x'])
                x2 = int(v_lines[c+1]['x'])
                
                # שמירת קואורדינטות מדויקות על התא עצמו!
                # זה התיקון הקריטי ל-OCR
                grid_obj.matrix[r][c].bbox = (x1, y1, x2, y2)
                
                cv2.rectangle(preview_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                if y2 > y1 and x2 > x1:
                    cell_roi = full_image[y1:y2, x1:x2]
                    self._analyze_cell_smart(grid_obj.matrix[r][c], cell_roi)

        return grid_obj, preview_img, full_image

    def _analyze_cell_smart(self, cell: Cell, cell_roi):
        if cell_roi.size == 0: return
        h, w, _ = cell_roi.shape
        margin_x = int(w * 0.25)
        margin_y = int(h * 0.25)
        inner = cell_roi[margin_y:h-margin_y, margin_x:w-margin_x]
        if inner.size == 0: inner = cell_roi

        hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)
        mean_sat = np.mean(hsv[:, :, 1])
        mean_val = np.mean(hsv[:, :, 2])
        
        if mean_val < 60:
            cell.type = CellType.BLOCK
            return

        if mean_sat > 25: 
            cell.type = CellType.CLUE
            gray_roi = cv2.cvtColor(cell_roi, cv2.COLOR_BGR2GRAY)
            cell.split_type = self._detect_split_morph(gray_roi)
            self._init_clue_slots(cell)
            return

        gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
        std_val = np.std(gray)
        
        if std_val < 12:
            cell.type = CellType.SOLUTION
            return
            
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        ink_density = cv2.countNonZero(thresh) / gray.size
        
        if ink_density < 0.05:
            cell.type = CellType.SOLUTION
        else:
            cell.type = CellType.CLUE
            gray_roi = cv2.cvtColor(cell_roi, cv2.COLOR_BGR2GRAY)
            cell.split_type = self._detect_split_morph(gray_roi)
            self._init_clue_slots(cell)

    def _detect_split_morph(self, cell_img):
        h, w = cell_img.shape
        if h < 10 or w < 10: return SplitType.NONE
        thresh = cv2.adaptiveThreshold(cell_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        m = 3
        inner = thresh[m:h-m, m:w-m]
        if inner.size == 0: return SplitType.NONE
        if cv2.countNonZero(inner) / inner.size > 0.5: return SplitType.NONE 
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w*0.7), 1))
        if cv2.countNonZero(cv2.morphologyEx(inner, cv2.MORPH_OPEN, hk)) > 0: return SplitType.HORIZONTAL
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(h*0.7)))
        if cv2.countNonZero(cv2.morphologyEx(inner, cv2.MORPH_OPEN, vk)) > 0: return SplitType.VERTICAL
        return SplitType.NONE
    
    def _init_clue_slots(self, cell):
        base_id = f"clue_{cell.row}_{cell.col}"
        if cell.split_type == SplitType.NONE:
            cell.clues.append(ClueMeta(id=f"{base_id}_full", sub_position="full"))
        elif cell.split_type == SplitType.HORIZONTAL:
            cell.clues.append(ClueMeta(id=f"{base_id}_top", sub_position="top"))
            cell.clues.append(ClueMeta(id=f"{base_id}_bottom", sub_position="bottom"))
        elif cell.split_type == SplitType.VERTICAL:
            cell.clues.append(ClueMeta(id=f"{base_id}_right", sub_position="right"))
            cell.clues.append(ClueMeta(id=f"{base_id}_left", sub_position="left"))