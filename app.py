import streamlit as st
import cv2
import numpy as np
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from services.vision_service import VisionService
from services.ocr_service_new import OcrService  # Phase 1: השתמש בגרסה החדשה
from models.grid import CellType
from database import PuzzleRepository

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
if 'loaded_puzzle_name' not in st.session_state:
    st.session_state.loaded_puzzle_name = None  # שם התשבץ שנטען מה-DB
if 'show_load_dialog' not in st.session_state:
    st.session_state.show_load_dialog = False
if 'show_save_dialog' not in st.session_state:
    st.session_state.show_save_dialog = False

# Repository לגישה ל-Database
puzzle_repo = PuzzleRepository()

# --- סרגל צד ---
with st.sidebar:
    st.header("1. העלאת תמונה")

    # כפתורי העלאה וטעינה
    upload_col, load_col = st.columns(2)
    with upload_col:
        uploaded_file = st.file_uploader("בחר קובץ", type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
    with load_col:
        if st.button("📂 טען תשבץ", use_container_width=True):
            st.session_state.show_load_dialog = True

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
            st.session_state.loaded_puzzle_name = None
            st.rerun()

# === דיאלוג טעינת תשבץ ===
if st.session_state.show_load_dialog:
    st.markdown("---")
    st.subheader("📂 טעינת תשבץ שמור")

    puzzles = puzzle_repo.list_puzzles()

    if not puzzles:
        st.info("אין תשבצים שמורים עדיין.")
        if st.button("סגור"):
            st.session_state.show_load_dialog = False
            st.rerun()
    else:
        # הצגת רשימת תשבצים
        puzzle_options = {f"{p['name']} ({p['rows']}x{p['cols']})": p['id'] for p in puzzles}

        selected = st.selectbox("בחר תשבץ:", options=list(puzzle_options.keys()))

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ טען", use_container_width=True):
                puzzle_id = puzzle_options[selected]
                try:
                    grid = puzzle_repo.load_puzzle_by_id(puzzle_id)
                    # שמירה ב-session_state
                    st.session_state.analyzed_grid = grid
                    st.session_state.puzzle_image = None  # אין תמונה בשמירה
                    st.session_state.loaded_puzzle_name = selected.split(" (")[0]
                    st.session_state.show_load_dialog = False
                    st.success(f"✅ תשבץ '{st.session_state.loaded_puzzle_name}' נטען בהצלחה!")
                    st.rerun()
                except Exception as e:
                    st.error(f"שגיאה בטעינה: {e}")

        with col2:
            if st.button("🗑️ מחק", use_container_width=True):
                puzzle_id = puzzle_options[selected]
                puzzle_repo.delete_puzzle(puzzle_id)
                st.success("התשבץ נמחק")
                st.rerun()

        with col3:
            if st.button("❌ ביטול", use_container_width=True):
                st.session_state.show_load_dialog = False
                st.rerun()

# === דיאלוג שמירת תשבץ ===
if st.session_state.show_save_dialog:
    st.markdown("---")
    st.subheader("💾 שמירת תשבץ")

    puzzle_name = st.text_input("שם התשבץ:", placeholder="לדוגמה: תשבץ יום שישי")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ שמור", use_container_width=True, disabled=not puzzle_name):
            if puzzle_name:
                try:
                    puzzle_repo.save_puzzle(
                        name=puzzle_name,
                        grid=st.session_state.analyzed_grid
                    )
                    st.session_state.loaded_puzzle_name = puzzle_name
                    st.session_state.show_save_dialog = False
                    st.success(f"✅ התשבץ '{puzzle_name}' נשמר בהצלחה!")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"שגיאה בשמירה: {e}")

    with col2:
        if st.button("❌ ביטול", use_container_width=True):
            st.session_state.show_save_dialog = False
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
                st.image(preview, channels="BGR", width="stretch")

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
            if st.session_state.puzzle_image is not None:
                st.image(st.session_state.puzzle_image, channels="BGR", width="stretch")
            
            grid_obj = st.session_state.analyzed_grid
            clues = sum(1 for r in grid_obj.matrix for c in r if c.type == CellType.CLUE)
            st.success(f"זוהו {clues} הגדרות")
            
            # ... (בתוך col2, אחרי שלב 2) ...

           
            # ... (בתוך col2 ב-app.py) ...

            st.divider()
            st.subheader("שלב 3: זיהוי ואימות ויזואלי")

            # Phase 2: בחירת ספק
            provider_option = st.radio(
                "בחר שיטת זיהוי:",
                ["☁️ Cloud (Google + Claude) - מומלץ", "💻 Local (Tesseract + Templates)"],
                horizontal=True
            )
            use_cloud = provider_option.startswith("☁️")

            if st.button("🧠 הפעל זיהוי + הצג חיתוכים", type="primary"):
                ocr_service = OcrService(use_cloud_services=use_cloud)
                # המרה ל-BGR כי כל הקוד מצפה לפורמט OpenCV
                image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                updated_grid = ocr_service.recognize_clues(
                    image_bgr,
                    st.session_state.analyzed_grid
                )
                st.session_state.analyzed_grid = updated_grid

                # שמירת הלוגים מה-batch_processor
                if hasattr(ocr_service, 'batch_processor') and ocr_service.batch_processor:
                    st.session_state.debug_logs = ocr_service.batch_processor.get_debug_logs()

                # לא עושים rerun - התוצאות יוצגו ישירות למטה
                st.success("✅ הזיהוי הושלם! גלול למטה לראות תוצאות.")
            
            # --- בחינה חוזרת של משבצת ---
            st.markdown("---")
            st.markdown("#### 🔄 בחינה חוזרת של משבצת")
            st.caption("הזן מיקום משבצת לבחינה מחדש (מתגבר על טעויות סטוכסטיות של המודל)")

            reexamine_cols = st.columns([1, 1, 2])
            with reexamine_cols[0]:
                reexamine_row = st.number_input("שורה", min_value=1, max_value=grid_obj.rows, value=1, key="reexamine_row")
            with reexamine_cols[1]:
                reexamine_col = st.number_input("עמודה", min_value=1, max_value=grid_obj.cols, value=1, key="reexamine_col")
            with reexamine_cols[2]:
                if st.button("🔄 בחן מחדש", type="secondary"):
                    # המרת למספור 0-based
                    row_idx = reexamine_row - 1
                    col_idx = reexamine_col - 1

                    cell = grid_obj.matrix[row_idx][col_idx]
                    if cell.type != CellType.CLUE:
                        st.error(f"משבצת ({reexamine_row},{reexamine_col}) אינה משבצת הגדרה!")
                    else:
                        with st.spinner(f"בוחן מחדש משבצת ({reexamine_row},{reexamine_col})..."):
                            # יצירת BatchProcessor חדש לבחינה
                            from services.batch_processor import BatchProcessor
                            from services.recognition_orchestrator import RecognitionOrchestrator
                            from config.cloud_config import get_cloud_config

                            # אם use_cloud=True, נשתמש ב-config הרגיל, אחרת נייצר config ריק
                            if use_cloud:
                                orchestrator = RecognitionOrchestrator()  # ישתמש ב-get_cloud_config() כברירת מחדל
                            else:
                                # יצירת config ללא cloud services
                                from config.cloud_config import CloudServicesConfig, GoogleVisionConfig, ClaudeVisionConfig
                                local_config = CloudServicesConfig(
                                    google=GoogleVisionConfig(api_key=None),
                                    claude=ClaudeVisionConfig(api_key=None)
                                )
                                orchestrator = RecognitionOrchestrator(config=local_config)

                            batch_processor = BatchProcessor(orchestrator=orchestrator)

                            # המרה ל-BGR
                            image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

                            # בחינה חוזרת
                            result = batch_processor.reexamine_cell(
                                image_bgr,
                                st.session_state.analyzed_grid,
                                row_idx,
                                col_idx
                            )

                            if result:
                                st.success(f"✅ משבצת ({reexamine_row},{reexamine_col}) נבחנה מחדש בהצלחה!")
                                # הצגת התוצאות החדשות
                                cell = grid_obj.matrix[row_idx][col_idx]
                                if hasattr(cell, 'parsed_clues') and cell.parsed_clues:
                                    for clue in cell.parsed_clues:
                                        st.info(f"חץ: {clue.get('path', 'none')}, טקסט: {clue.get('text', '')[:50]}")
                                st.rerun()
                            else:
                                st.error("שגיאה בבחינה חוזרת")

            st.markdown("---")

            # --- בניית הטבלה עם התמונות ---
            data = []
            grid_obj = st.session_state.analyzed_grid

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

                        # שליפת התמונות (אם קיימות)
                        img_data = getattr(cell, 'debug_image', None)
                        arrow_img_data = getattr(cell, 'arrow_debug_image', None)

                        for clue in cell.parsed_clues:
                            # Phase 1: הוספת confidence scores
                            confidence = clue.get('confidence', 0.0)
                            ocr_conf = clue.get('ocr_confidence', 0.0)
                            arrow_conf = clue.get('arrow_confidence', 0.0)

                            # מידע אופסט חדש
                            answer_start = clue.get('answer_start')
                            writing_dir = clue.get('writing_direction', '')
                            answer_length = clue.get('answer_length', 0)
                            zone = clue.get('zone', 'full')

                            # פורמט תחילת תשובה
                            start_str = f"({answer_start[0]+1},{answer_start[1]+1})" if answer_start else "-"

                            # אייקון כיוון כתיבה
                            dir_icons = {'down': '↓', 'up': '↑', 'right': '→', 'left': '←'}
                            dir_icon = dir_icons.get(writing_dir, '')

                            data.append({
                                "תמונה OCR": img_data,
                                "תמונה חצים": arrow_img_data,
                                "מיקום": f"({r+1},{c+1})",
                                "אזור": zone,
                                "תחילה": start_str,
                                "כיוון": dir_icon,
                                "אורך": answer_length if answer_length > 0 else "-",
                                "טקסט": clue.get('text', ''),
                                "ביטחון": confidence,
                                "OCR": ocr_conf,
                                "Arrow": arrow_conf
                            })

            # הצג דיבוג
            st.caption(f"נסרקו {cells_checked} תאים, נמצאו {cells_with_clues} עם parsed_clues")

            if data:
                # כותרת + כפתור שמירה
                title_col, save_col = st.columns([3, 1])
                with title_col:
                    st.write(f"### תוצאות ({len(data)} הגדרות):")
                with save_col:
                    if st.session_state.loaded_puzzle_name:
                        st.caption(f"📁 {st.session_state.loaded_puzzle_name}")
                    else:
                        if st.button("💾 שמור תשבץ", use_container_width=True):
                            st.session_state.show_save_dialog = True
                            st.rerun()

                # קונפיגורציה לטבלה
                st.dataframe(
                    data,
                    column_config={
                        "תמונה OCR": st.column_config.ImageColumn(
                            "תמונה ל-OCR",
                            help="התמונה המדויקת שנשלחה לזיהוי טקסט (Google Vision)",
                            width="small"
                        ),
                        "תמונה חצים": st.column_config.ImageColumn(
                            "תמונה לחצים",
                            help="התמונה המורחבת שנשלחה לזיהוי חצים (Claude)",
                            width="medium"
                        ),
                        "מיקום": st.column_config.TextColumn("מיקום", width="small"),
                        "אזור": st.column_config.TextColumn("אזור", width="small", help="full/top/bottom/left/right"),
                        "תחילה": st.column_config.TextColumn("תחילת תשובה", width="small", help="המשבצת בה מתחילה התשובה"),
                        "כיוון": st.column_config.TextColumn("כיוון", width="small", help="כיוון כתיבת התשובה"),
                        "אורך": st.column_config.NumberColumn("אורך", width="small", help="מספר אותיות בתשובה"),
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
                    width='stretch',
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

            # === לוגים מפורטים לדיבוג ===
            if 'debug_logs' in st.session_state and st.session_state.debug_logs:
                with st.expander("🔍 לוגים מפורטים - חישוב אופסטים", expanded=False):
                    debug_logs = st.session_state.debug_logs

                    # סיכום בעיות
                    problems = [log for log in debug_logs if log['status'] == 'PROBLEM']
                    ok_count = len(debug_logs) - len(problems)

                    if problems:
                        st.error(f"⚠️ נמצאו {len(problems)} בעיות בחישוב אופסטים (מתוך {len(debug_logs)} הגדרות)")
                    else:
                        st.success(f"✅ כל {len(debug_logs)} ההגדרות חושבו בהצלחה")

                    # טבלת לוגים
                    st.dataframe(
                        debug_logs,
                        column_config={
                            "source_cell": st.column_config.TextColumn("משבצת מקור", width="small"),
                            "text": st.column_config.TextColumn("טקסט", width="medium"),
                            "exit_side": st.column_config.TextColumn("פאת יציאה", width="small", help="מאיזה צד החץ יוצא מהמשבצת"),
                            "arrowhead": st.column_config.TextColumn("כיוון חץ", width="small", help="לאן ראש החץ מצביע"),
                            "arrow_direction": st.column_config.TextColumn("סוג חץ", width="small"),
                            "arrow_position": st.column_config.TextColumn("מיקום חץ", width="small"),
                            "answer_start": st.column_config.TextColumn("תחילת תשובה", width="small"),
                            "writing_direction": st.column_config.TextColumn("כיוון כתיבה", width="small"),
                            "answer_length": st.column_config.NumberColumn("אורך", width="small"),
                            "start_cell_type": st.column_config.TextColumn("סוג משבצת התחלה", width="small"),
                            "status": st.column_config.TextColumn("סטטוס", width="small"),
                        },
                        width='stretch',
                        hide_index=True
                    )

                    # הסבר על בעיות נפוצות
                    if problems:
                        st.markdown("""
                        **בעיות נפוצות:**
                        - `out_of_bounds` - משבצת ההתחלה מחוץ לגריד
                        - `clue` - משבצת ההתחלה היא הגדרה (לא פתרון)
                        - `block` - משבצת ההתחלה שחורה
                        """)

    # === Phase 3: מאגר הגדרות ופתרון ===
    st.divider()
    st.subheader("🧠 שלב 3: פתרון התשבץ")

    # בדיקה אם יש נתונים
    if st.session_state.analyzed_grid and data:
        from services.clue_database import ClueDatabase
        from services.solution_grid import SolutionGrid
        from services.clue_solver import ClueSolver
        from services.puzzle_solver import PuzzleSolver
        from config.cloud_config import get_cloud_config

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 בנה מאגר הגדרות", type="primary"):
                with st.spinner("בונה מאגר הגדרות..."):
                    clue_db = ClueDatabase()
                    clue_db.build_from_grid(st.session_state.analyzed_grid)
                    st.session_state.clue_database = clue_db

                    # סטטיסטיקות
                    stats = clue_db.get_statistics()
                    st.success(f"""
                    **מאגר נבנה בהצלחה!**
                    - סה"כ הגדרות: {stats['total_clues']}
                    - עם אורך תשובה: {stats['with_answer_length']}
                    - עם אותיות ידועות: {stats['with_known_letters']}
                    - אורך ממוצע: {stats['avg_answer_length']:.1f}
                    """)

        with col2:
            # הערה: הפותר האינטראקטיבי נמצא בשלב 4 למטה
            if 'clue_database' in st.session_state and st.session_state.clue_database:
                st.info("👇 לחץ על 'פתח פותר אינטראקטיבי' למטה להתחיל לפתור")

        # הצגת מאגר ההגדרות
        if 'clue_database' in st.session_state and st.session_state.clue_database:
            clue_db = st.session_state.clue_database

            with st.expander("📋 מאגר הגדרות", expanded=False):
                clue_data = []
                for clue in clue_db.clues:
                    constraint = clue.get_constraint_string()
                    clue_data.append({
                        "ID": clue.id,
                        "מיקום": f"({clue.source_cell[0]+1},{clue.source_cell[1]+1})",
                        "אזור": clue.zone,
                        "טקסט": clue.text[:30] + "..." if len(clue.text) > 30 else clue.text,
                        "חץ": clue.arrow_direction,
                        "תחילה": f"({clue.answer_start_cell[0]+1},{clue.answer_start_cell[1]+1})" if clue.answer_start_cell else "-",
                        "אורך": clue.answer_length,
                        "אילוצים": constraint if constraint else "-",
                        "נפתר": "✅" if clue.is_solved else "❌",
                        "תשובה": clue.chosen_answer or "-"
                    })

                st.dataframe(clue_data, width='stretch', hide_index=True)

        # הצגת גריד הפתרון
        if 'solution_grid' in st.session_state and st.session_state.solution_grid:
            solution = st.session_state.solution_grid
            grid_obj = st.session_state.analyzed_grid

            with st.expander("🔤 גריד פתרון", expanded=True):
                # יצירת טבלת HTML לגריד
                # direction: ltr כי אנחנו רוצים שעמודה 0 תהיה משמאל (כמו בתשבץ אמיתי)
                grid_html = "<table style='border-collapse: collapse; direction: ltr; margin: 0 auto;'>"
                for row in range(solution.rows):
                    grid_html += "<tr>"
                    for col in range(solution.cols):
                        cell = solution.get_cell(row, col)
                        letter = cell.letter if cell and cell.letter else ""

                        # צביעה לפי סוג המשבצת
                        original_cell = grid_obj.matrix[row][col]
                        cell_content = letter
                        font_size = "20px"

                        if original_cell.type == CellType.BLOCK:
                            bg_color = "#333"
                            text_color = "#333"
                        elif original_cell.type == CellType.CLUE:
                            bg_color = "#e0e0ff"
                            text_color = "#333"
                            font_size = "8px"
                            # הוספת טקסט ההגדרה
                            if hasattr(original_cell, 'parsed_clues') and original_cell.parsed_clues:
                                clue_texts = [c.get('text', '')[:15] for c in original_cell.parsed_clues]
                                cell_content = '<br>'.join(clue_texts)
                            else:
                                cell_content = "הגדרה"
                        else:
                            # SOLUTION
                            if cell and cell.is_conflict:
                                bg_color = "#ffcccc"  # אדום לסתירה
                            elif letter:
                                bg_color = "#ccffcc"  # ירוק לאות
                            else:
                                bg_color = "#fff"  # לבן לריק
                            text_color = "#000"

                        # Build cell style
                        cell_style = f"width:45px;height:45px;border:1px solid #999;text-align:center;font-size:{font_size};font-weight:bold;background-color:{bg_color};color:{text_color};vertical-align:middle;overflow:hidden;padding:2px;"
                        grid_html += f"<td style='{cell_style}'>{cell_content}</td>"
                    grid_html += "</tr>"
                grid_html += "</table>"

                st.markdown(grid_html, unsafe_allow_html=True)

                # סטטיסטיקות
                stats = solution.get_statistics()
                st.caption(f"""
                מילוי: {stats['completion_percentage']:.0f}% |
                משבצות מלאות: {stats['filled_cells']}/{stats['total_cells']} |
                סתירות: {stats['conflicts']}
                """)

        # === Phase 4: פותר אינטראקטיבי ===
        st.divider()
        st.subheader("🎮 שלב 4: פתרון אינטראקטיבי")

        if 'clue_database' in st.session_state and st.session_state.clue_database:
            from ui import SolverView, SolverViewConfig, SolverUIState, SolverMode

            # Initialize interactive solver state
            if 'interactive_solver_ready' not in st.session_state:
                st.session_state.interactive_solver_ready = False

            if st.button("🎯 פתח פותר אינטראקטיבי", type="primary"):
                st.session_state.interactive_solver_ready = True

            if st.session_state.interactive_solver_ready:
                # Prepare grid data for display
                grid_obj = st.session_state.analyzed_grid
                grid_data = []

                for row_idx in range(grid_obj.rows):
                    row_data = []
                    for col_idx in range(grid_obj.cols):
                        cell = grid_obj.matrix[row_idx][col_idx]
                        cell_info = {
                            'type': cell.type,
                            'text': ''
                        }

                        # For clue cells, add text
                        if cell.type == CellType.CLUE:
                            if hasattr(cell, 'parsed_clues') and cell.parsed_clues:
                                texts = [c.get('text', '')[:10] for c in cell.parsed_clues]
                                cell_info['text'] = ' / '.join(texts)

                        row_data.append(cell_info)
                    grid_data.append(row_data)

                # Prepare clues list
                clue_db = st.session_state.clue_database
                clues_list = []

                for clue in clue_db.clues:
                    clues_list.append({
                        'id': clue.id,
                        'text': clue.text,
                        'answer_length': clue.answer_length,
                        'answer_cells': clue.answer_cells,
                        'arrow_direction': clue.arrow_direction,
                        'source_cell': clue.source_cell,
                        'zone': clue.zone
                    })

                # Get or create puzzle solver
                if 'puzzle_solver' not in st.session_state:
                    from services.puzzle_solver import PuzzleSolver
                    from services.solution_grid import SolutionGrid
                    from services.clue_solver import ClueSolver
                    from config.cloud_config import get_cloud_config

                    config = get_cloud_config()
                    solution = SolutionGrid(grid_obj.rows, grid_obj.cols)
                    solver = ClueSolver(api_key=config.claude.api_key, model=config.claude.model)
                    puzzle_solver = PuzzleSolver(clue_db, solution, solver)
                    st.session_state.puzzle_solver = puzzle_solver
                    st.session_state.solution_grid = solution

                # Configure view
                view_config = SolverViewConfig(
                    cell_size=40,
                    letter_delay_ms=150,
                    show_stats=True,
                    show_manual_edit=True
                )

                # Render interactive solver
                st.markdown("---")
                view = SolverView(
                    grid_data=grid_data,
                    clues=clues_list,
                    puzzle_solver=st.session_state.puzzle_solver,
                    config=view_config
                )
                view.render()

        else:
            st.info("בנה קודם את מאגר ההגדרות כדי להפעיל פותר אינטראקטיבי")

    else:
        st.info("👆 הפעל קודם את זיהוי ההגדרות כדי להמשיך לפתרון")

# === תצוגת תשבץ שנטען מה-DB (ללא uploaded_file) ===
elif st.session_state.analyzed_grid is not None and st.session_state.loaded_puzzle_name:
    st.success(f"📁 תשבץ נטען: **{st.session_state.loaded_puzzle_name}**")

    grid_obj = st.session_state.analyzed_grid

    st.subheader("תוצאות הזיהוי")

    # בניית טבלת תוצאות
    data = []
    for r in range(grid_obj.rows):
        for c in range(grid_obj.cols):
            cell = grid_obj.matrix[r][c]
            if hasattr(cell, 'parsed_clues') and cell.parsed_clues:
                for clue in cell.parsed_clues:
                    writing_dir = clue.get('writing_direction', '')
                    answer_start = clue.get('answer_start')
                    answer_length = clue.get('answer_length', 0)

                    dir_icons = {'down': '↓', 'up': '↑', 'right': '→', 'left': '←'}
                    dir_icon = dir_icons.get(writing_dir, '')
                    start_str = f"({answer_start[0]+1},{answer_start[1]+1})" if answer_start else "-"

                    data.append({
                        "מיקום": f"({r+1},{c+1})",
                        "תחילה": start_str,
                        "כיוון": dir_icon,
                        "אורך": answer_length if answer_length > 0 else "-",
                        "טקסט": clue.get('text', '')[:40],
                    })

    if data:
        st.write(f"**{len(data)} הגדרות**")
        st.dataframe(data, hide_index=True, height=600)
    else:
        st.warning("לא נמצאו הגדרות בתשבץ זה")

else:
    st.info("👈 העלה תמונת תשבץ או טען תשבץ שמור כדי להתחיל")