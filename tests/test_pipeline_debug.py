"""
Pipeline Debug - בדיקת כל שלב בנפרד
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import cv2
import numpy as np
from PIL import Image

print("=" * 60)
print("PIPELINE DEBUG")
print("=" * 60)

# יצירת תמונה בדיקה שמדמה משבצת תשבץ עם טקסט עברי
print("\n[1] Creating test cell image with Hebrew text...")

# Create white background
cell_img = np.ones((80, 120, 3), dtype=np.uint8) * 255

# Add Hebrew text using PIL (better Hebrew support)
from PIL import Image, ImageDraw, ImageFont
pil_img = Image.fromarray(cv2.cvtColor(cell_img, cv2.COLOR_BGR2RGB))
draw = ImageDraw.Draw(pil_img)

try:
    # Try to find a Hebrew-supporting font
    font = ImageFont.truetype("arial.ttf", 24)
except:
    font = ImageFont.load_default()

draw.text((10, 25), "בדיקה", fill='black', font=font)

# Convert back to OpenCV format
cell_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

# Add a simple arrow shape
cv2.arrowedLine(cell_img, (100, 70), (100, 20), (0, 0, 0), 2)

cv2.imwrite("debug_cell.png", cell_img)
print(f"  Created test image: debug_cell.png")
print(f"  Image shape: {cell_img.shape}")
print(f"  Image dtype: {cell_img.dtype}")

# ========================================
print("\n[2] Testing OCR Engine Manager...")
# ========================================

from services.ocr_engine_manager import OcrEngineManager

ocr_manager = OcrEngineManager()
ocr_manager.initialize_engines()

print("\n  [2.1] Testing preprocess_image...")
preprocessed = ocr_manager.preprocess_image(cell_img)
print(f"    Input shape: {cell_img.shape}")
print(f"    Output shape: {preprocessed.shape}")
cv2.imwrite("debug_preprocessed.png", preprocessed)
print(f"    Saved: debug_preprocessed.png")

print("\n  [2.2] Testing recognize_text...")
ocr_result = ocr_manager.recognize_text(preprocessed)
print(f"    Text: '{ocr_result.text}'")
print(f"    Confidence: {ocr_result.confidence:.3f}")
print(f"    Engine: {ocr_result.engine_used}")
print(f"    Raw result: {ocr_result.raw_result}")

# Also test on original (not preprocessed)
print("\n  [2.3] Testing recognize_text on ORIGINAL image...")
ocr_result_orig = ocr_manager.recognize_text(cell_img)
print(f"    Text: '{ocr_result_orig.text}'")
print(f"    Confidence: {ocr_result_orig.confidence:.3f}")

# ========================================
print("\n[3] Testing Arrow Detector...")
# ========================================

from services.arrow_detector import ArrowDetector

arrow_detector = ArrowDetector()

arrow_result = arrow_detector.detect_arrow(cell_img, (0, 0, 120, 80))
print(f"  Direction: {arrow_result.direction}")
print(f"  Confidence: {arrow_result.confidence:.3f}")
print(f"  Template matched: {arrow_result.template_matched}")

# ========================================
print("\n[4] Testing Confidence Scorer...")
# ========================================

from services.confidence_scorer import ConfidenceScorer

scorer = ConfidenceScorer()
confidence = scorer.calculate_confidence(ocr_result, arrow_result, cell_img)
print(f"  Overall: {confidence.overall:.3f}")
print(f"  Level: {confidence.level}")

# ========================================
print("\n[5] Testing Full Pipeline (BatchProcessor._process_single_cell)...")
# ========================================

from services.batch_processor import BatchProcessor

# Create mock task
mock_task = {
    'row': 0,
    'col': 0,
    'image': cell_img,
    'bbox': (0, 0, 120, 80),
    'cell': None
}

batch_processor = BatchProcessor(ocr_manager, arrow_detector, scorer)

result = batch_processor._process_single_cell(mock_task)

print(f"  Has ocr_result: {result.ocr_result is not None}")
print(f"  Has arrow_result: {result.arrow_result is not None}")
print(f"  Has confidence: {result.confidence is not None}")
print(f"  Has error: {result.error}")

if result.ocr_result:
    print(f"  OCR text: '{result.ocr_result.text}'")
    print(f"  OCR confidence: {result.ocr_result.confidence:.3f}")

if result.arrow_result:
    print(f"  Arrow direction: {result.arrow_result.direction}")
    print(f"  Arrow confidence: {result.arrow_result.confidence:.3f}")

# ========================================
print("\n[6] Testing parsed_clues extraction...")
# ========================================

ocr_text = result.ocr_result.text if result.ocr_result else ""
ocr_conf = result.ocr_result.confidence if result.ocr_result else 0.0
arrow_dir = result.arrow_result.direction if result.arrow_result else 'none'
arrow_conf = result.arrow_result.confidence if result.arrow_result else 0.0
overall_conf = result.confidence.overall if result.confidence else 0.0

print(f"  text: '{ocr_text}'")
print(f"  path: '{arrow_dir}'")
print(f"  confidence: {overall_conf:.3f}")
print(f"  ocr_confidence: {ocr_conf:.3f}")
print(f"  arrow_confidence: {arrow_conf:.3f}")

# ========================================
print("\n[7] Testing debug_image generation...")
# ========================================

if result.cell_image is not None:
    import base64
    _, buffer = cv2.imencode('.png', result.cell_image)
    b64_img = base64.b64encode(buffer).decode('utf-8')
    debug_image = f"data:image/png;base64,{b64_img}"
    print(f"  debug_image length: {len(debug_image)}")
    print(f"  debug_image starts with: {debug_image[:50]}...")
else:
    print("  ERROR: cell_image is None!")

print("\n" + "=" * 60)
print("PIPELINE DEBUG COMPLETE")
print("=" * 60)
