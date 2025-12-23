import streamlit as st
import cv2
import numpy as np
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from services.vision_service import VisionService
from services.ocr_service_new import OcrService  # Phase 1: השתמש בגרסה החדשה
from models.grid import CellType

st.set_page_config(page_title="Crossword Architect", layout="wide")
st.title("AI Crossword Architect 🧩")

vision_service = VisionService()

# --- ניהול זיכרון (Session State) ---
if 'analyzed_grid' not in st.session_state:
    st.session_state.analyzed_grid = None
if 'puzzle_image' not in st.session_state:
    st.session_state.puzzle_image = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = 'coarse' # coarse (מלבן) או fine (קווים)
if 'lines_data' not in st.session_state:
    st.session_state.lines_data = None # שומר את הקווים למצב העדין

# --- סרגל צד ---
with st.sidebar:
    st.header("1. העלאת תמונה")
    uploaded_file = st.file_uploader("בחר קובץ", type=['jpg', 'png', 'jpeg'])
    
    if uploaded_file:
        st.divider()
        st.header("2. הגדרת גריד")
        # שימוש ב-key כדי למנוע התנגשויות בריענון
        rows = st.number_input("שורות", 3, 40, 13, key="input_rows")
        cols = st.number_input("עמודות", 3, 40, 13, key="input_cols")
        
        # כפתור איפוס למקרה שמסתבכים
        st.divider()
        if st.button("🔄 אפס גריד להתחלה"):
            st.session_state.edit_mode = 'coarse'
            st.session_state.lines_data = None
            st.session_state.analyzed_grid = None
            st.rerun()

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    # המרה ל-RGB אם צריך (למקרה של RGBA או אחר)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    w, h = image.size

    # חישוב גודל תצוגה
    canvas_width = 800
    canvas_height = int(h * (canvas_width / w))
    scale_x = w / canvas_width
    scale_y = h / canvas_height

    # יצירת תמונה מוקטנת לתצוגה בקנבס
    display_image = image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
    
    col1, col2 = st.columns([2, 1])
    
    # === עמודה 1: הקנבס והעריכה ===
    with col1:
        st.subheader("שלב 1: התאמת גריד")
        
        # --- מצב א': מתיחה גסה (Coarse) ---
        if st.session_state.edit_mode == 'coarse':
            st.info("1. גרור את המסגרת האדומה שתכסה את כל התשחץ.\n2. לחץ על 'פרק לקווים' לכיוונון עדין.")
            
            # מלבן ברירת מחדל
            default_rect = {
                "type": "rect", "left": 50, "top": 50, 
                "width": canvas_width-100, "height": canvas_height-100,
                "fill": "rgba(255, 0, 0, 0.1)", "stroke": "red", "strokeWidth": 2
            }
            
            initial_drawing = {"version": "4.4.0", "objects": [default_rect]} if "canvas_json" not in st.session_state else None
            
            canvas_result = st_canvas(
                fill_color="rgba(255, 0, 0, 0.1)",
                stroke_color="red",
                background_image=display_image,
                update_streamlit=True,
                height=canvas_height,
                width=canvas_width,
                drawing_mode="transform",
                initial_drawing=initial_drawing,
                key="canvas_coarse",
            )
            
            # חישוב קווים אוטומטי לתצוגה מקדימה
            if canvas_result.json_data and len(canvas_result.json_data["objects"]) > 0:
                rect = canvas_result.json_data["objects"][0]
                
                # חישוב המיקום האמיתי בתמונה
                real_rect = {
                    "left": rect["left"] * scale_x,
                    "top": rect["top"] * scale_y,
                    "width": rect["width"] * scale_x * rect["scaleX"],
                    "height": rect["height"] * scale_y * rect["scaleY"]
                }
                
                # כפתור מעבר למצב עדין
                if st.button("🔨 פרק לקווים (Fine Tune)", type="primary"):
                    # כאן אנחנו "מפוצצים" את המלבן לקווים
                    st.session_state.lines_data = []
                    
                    # חישוב מיקומי הקווים (בקואורדינטות קנבס)
                    r_x = rect["left"]
                    r_y = rect["top"]
                    r_w = rect["width"] * rect["scaleX"]
                    r_h = rect["height"] * rect["scaleY"]
                    
                    # יצירת קווים אופקיים
                    for r in range(rows + 1):
                        y_pos = r_y + (r * (r_h / rows))
                        st.session_state.lines_data.append({
                            "type": "line", "x1": r_x, "y1": y_pos, "x2": r_x + r_w, "y2": y_pos,
                            "stroke": "red", "strokeWidth": 2, "selectable": True
                        })
                        
                    # יצירת קווים אנכיים
                    for c in range(cols + 1):
                        x_pos = r_x + (c * (r_w / cols))
                        st.session_state.lines_data.append({
                            "type": "line", "x1": x_pos, "y1": r_y, "x2": x_pos, "y2": r_y + r_h,
                            "stroke": "red", "strokeWidth": 2, "selectable": True
                        })
                    
                    st.session_state.edit_mode = 'fine'
                    st.rerun()
                
                # תצוגה מקדימה פאסיבית (ירוק)
                preview = vision_service.generate_preview(image, real_rect, rows, cols)
                st.image(preview, channels="BGR", use_container_width=True)

        # --- מצב ב': כיוונון עדין (Fine) ---
        elif st.session_state.edit_mode == 'fine':
            st.info("כעת כל קו הוא עצמאי! תפוס והזז קווים ספציפיים כדי לתקן עיוותים.")
            
            # טעינת הקווים שיצרנו
            initial_lines = {"version": "4.4.0", "objects": st.session_state.lines_data}
            
            canvas_result = st_canvas(
                fill_color="rgba(0, 0, 0, 0)",
                stroke_color="red",
                background_image=display_image,
                update_streamlit=True,
                height=canvas_height,
                width=canvas_width,
                drawing_mode="transform", # מאפשר גרירה של הקווים
                initial_drawing=initial_lines,
                key="canvas_fine",
            )
            
            if st.button("✅ סיים ונתח גריד", type="primary"):
                if canvas_result.json_data:
                    # איסוף המיקום הסופי של הקווים
                    h_lines_final = []
                    v_lines_final = []
                    
                    objects = canvas_result.json_data["objects"]
                    for obj in objects:
                        if obj["type"] == "line":
                            # בדיקה אם זה קו אופקי או אנכי לפי הפרופורציות שלו
                            # קו אופקי: רוחב גדול מגובה
                            o_w = abs(obj["x2"] - obj["x1"])
                            o_h = abs(obj["y2"] - obj["y1"])
                            
                            # המרה לקואורדינטות תמונה מקורית
                            # שים לב: ב-FabricJS המיקום הוא left/top
                            real_x = obj["left"] * scale_x
                            real_y = obj["top"] * scale_y
                            
                            if o_w > o_h: # אופקי
                                h_lines_final.append({'y': real_y})
                            else: # אנכי
                                v_lines_final.append({'x': real_x})
                    
                    with st.spinner("מנתח גריד..."):
                        grid, p_img, _ = vision_service.process_lines_grid(
                            image, h_lines_final, v_lines_final, rows, cols
                        )
                        st.session_state.analyzed_grid = grid
                        st.session_state.puzzle_image = p_img
                        st.rerun()

    # === עמודה 2: תוצאות ===
    with col2:
        if st.session_state.analyzed_grid:
            st.subheader("שלב 2: תוצאות")
            st.image(st.session_state.puzzle_image, channels="BGR", use_container_width=True)
            
            grid_obj = st.session_state.analyzed_grid
            clues = sum(1 for r in grid_obj.matrix for c in r if c.type == CellType.CLUE)
            st.success(f"זוהו {clues} הגדרות")
            
            # ... (בתוך col2, אחרי שלב 2) ...

           
            # ... (בתוך col2 ב-app.py) ...

            st.divider()
            st.subheader("שלב 3: זיהוי ואימות ויזואלי")

            # Phase 1: אופציה לבחירה בין Pipeline מקומי ל-GPT-4
            use_local = st.checkbox(
                "🚀 השתמש ב-Pipeline מקומי (Phase 1 - מהיר וחינמי)",
                value=True,
                help="Pipeline חדש עם EasyOCR + Template Matching"
            )

            if st.button("🧠 הפעל זיהוי + הצג חיתוכים", type="primary"):
                ocr_service = OcrService(use_local_ocr=use_local)
                # המרה ל-BGR כי כל הקוד מצפה לפורמט OpenCV
                image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                updated_grid = ocr_service.recognize_clues(
                    image_bgr,
                    st.session_state.analyzed_grid
                )
                st.session_state.analyzed_grid = updated_grid
                # לא עושים rerun - התוצאות יוצגו ישירות למטה
                st.success("✅ הזיהוי הושלם! גלול למטה לראות תוצאות.")
            
            # --- בניית הטבלה עם התמונות ---
            data = []
            grid_obj = st.session_state.analyzed_grid

            # מיפוי חצים לאייקונים - תואם לשמות מ-ArrowDetector
            arrow_icons = {
                'none': '❓',
                # Straight arrows
                'straight-left': '⬅️',
                'straight-right': '➡️',
                'straight-down': '⬇️',
                'straight-up': '⬆️',
                # Step arrows
                'start-up-turn-right': '↗️',
                'start-up-turn-left': '↖️',
                'start-down-turn-right': '↘️',
                'start-down-turn-left': '↙️',
                'start-left-turn-down': '↙️',
                'start-left-turn-up': '↖️',
                'start-right-turn-down': '↘️',
                'start-right-turn-up': '↗️',
                # Legacy names (backward compatibility)
                'DOWN': '⬇️', 'UP': '⬆️', 'LEFT': '⬅️', 'RIGHT': '➡️',
            }

            # דיבוג: סריקת הגריד
            cells_checked = 0
            cells_with_clues = 0

            for r in range(grid_obj.rows):
                for c in range(grid_obj.cols):
                    cell = grid_obj.matrix[r][c]
                    cells_checked += 1

                    # בדיקה אם יש מידע מנותח
                    if hasattr(cell, 'parsed_clues') and cell.parsed_clues:
                        cells_with_clues += 1
                        is_split = len(cell.parsed_clues) > 1

                        # שליפת התמונה (אם קיימת)
                        img_data = getattr(cell, 'debug_image', None)

                        for clue in cell.parsed_clues:
                            path_str = clue.get('path', 'none')
                            icon = arrow_icons.get(path_str, '❓')

                            # Phase 1: הוספת confidence scores
                            confidence = clue.get('confidence', 0.0)
                            ocr_conf = clue.get('ocr_confidence', 0.0)
                            arrow_conf = clue.get('arrow_confidence', 0.0)

                            data.append({
                                "תמונה": img_data,
                                "מיקום": f"({r+1},{c+1})",
                                "מצב": "מפוצל" if is_split else "יחיד",
                                "חץ": f"{icon}",
                                "טקסט": clue.get('text', ''),
                                "ביטחון": confidence,
                                "OCR": ocr_conf,
                                "Arrow": arrow_conf
                            })

            # הצג דיבוג
            st.caption(f"נסרקו {cells_checked} תאים, נמצאו {cells_with_clues} עם parsed_clues")

            if data:
                st.write(f"### תוצאות ({len(data)} הגדרות):")

                # קונפיגורציה לטבלה
                st.dataframe(
                    data,
                    column_config={
                        "תמונה": st.column_config.ImageColumn(
                            "המשבצת שנסרקה",
                            help="כך המודל 'ראה' את המשבצת",
                            width="small"
                        ),
                        "מיקום": st.column_config.TextColumn("מיקום", width="small"),
                        "מצב": st.column_config.TextColumn("מצב", width="small"),
                        "חץ": st.column_config.TextColumn("מסלול", width="small"),
                        "טקסט": st.column_config.TextColumn("תוכן", width="large"),
                        "ביטחון": st.column_config.ProgressColumn(
                            "Confidence",
                            help="ציון ביטחון כולל",
                            format="%.2f",
                            min_value=0,
                            max_value=1
                        ),
                        "OCR": st.column_config.ProgressColumn(
                            "OCR",
                            help="ביטחון זיהוי טקסט",
                            format="%.2f",
                            min_value=0,
                            max_value=1
                        ),
                        "Arrow": st.column_config.ProgressColumn(
                            "חץ",
                            help="ביטחון זיהוי חץ",
                            format="%.2f",
                            min_value=0,
                            max_value=1
                        ),
                    },
                    use_container_width=True,
                    height=800,
                    hide_index=True
                )
            else:
                if st.session_state.analyzed_grid:
                    # דיבוג: בדיקה למה אין תוצאות
                    grid_obj = st.session_state.analyzed_grid
                    cells_with_clues = sum(1 for r in range(grid_obj.rows) for c in range(grid_obj.cols)
                                          if hasattr(grid_obj.matrix[r][c], 'parsed_clues') and grid_obj.matrix[r][c].parsed_clues)
                    cells_with_result = sum(1 for r in range(grid_obj.rows) for c in range(grid_obj.cols)
                                           if hasattr(grid_obj.matrix[r][c], 'recognition_result'))

                    st.warning(f"""
                    **לא נמצאו תוצאות להצגה.**

                    דיבוג:
                    - משבצות עם parsed_clues: {cells_with_clues}
                    - משבצות עם recognition_result: {cells_with_result}

                    לחץ על **'הפעל זיהוי'** כדי לעבד את המשבצות.
                    """)