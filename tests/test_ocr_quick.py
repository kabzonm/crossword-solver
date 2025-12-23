"""
Quick OCR Test Script
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import cv2
import numpy as np
from PIL import Image

print("Testing Tesseract OCR...")
print("=" * 50)

# Test 1: Import
try:
    import pytesseract
    print("✓ pytesseract imported")
except ImportError as e:
    print(f"✗ Failed to import pytesseract: {e}")
    exit(1)

# Test 2: Set path
import os
common_paths = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
]
for path in common_paths:
    if os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        print(f"✓ Found Tesseract at: {path}")
        break

# Test 3: Check languages
try:
    langs = pytesseract.get_languages()
    print(f"✓ Available languages: {langs}")
    if 'heb' in langs:
        print("✓ Hebrew is available!")
    else:
        print("⚠ Hebrew NOT found - install it!")
except Exception as e:
    print(f"✗ Could not get languages: {e}")

# Test 4: Create test image with Hebrew text
print("\n" + "=" * 50)
print("Creating test image with Hebrew text...")

# Create a white image
img = np.ones((100, 300, 3), dtype=np.uint8) * 255

# Draw Hebrew text (using PIL which supports Hebrew better)
from PIL import Image, ImageDraw, ImageFont
pil_img = Image.new('RGB', (300, 100), color='white')
draw = ImageDraw.Draw(pil_img)

# Try to use a Hebrew font
try:
    font = ImageFont.truetype("arial.ttf", 36)
except:
    font = ImageFont.load_default()

# Draw text
draw.text((50, 30), "שלום עולם", fill='black', font=font)

# Convert to numpy
test_image = np.array(pil_img)
test_image_bgr = cv2.cvtColor(test_image, cv2.COLOR_RGB2BGR)

# Save for debug
cv2.imwrite("test_hebrew.png", test_image_bgr)
print("✓ Saved test image to test_hebrew.png")

# Test 5: OCR on the test image
print("\n" + "=" * 50)
print("Running OCR on test image...")

try:
    # Direct with PIL image
    text = pytesseract.image_to_string(pil_img, lang='heb', config='--psm 6')
    print(f"✓ OCR result: '{text.strip()}'")

    # With confidence data
    data = pytesseract.image_to_data(pil_img, lang='heb', config='--psm 6', output_type=pytesseract.Output.DICT)
    confidences = [int(c) for c, t in zip(data['conf'], data['text']) if int(c) > 0 and t.strip()]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    print(f"✓ Average confidence: {avg_conf:.1f}%")
    print(f"✓ Detected words: {[t for t in data['text'] if t.strip()]}")

except Exception as e:
    print(f"✗ OCR failed: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Test with OcrEngineManager
print("\n" + "=" * 50)
print("Testing OcrEngineManager...")

try:
    from services.ocr_engine_manager import OcrEngineManager

    manager = OcrEngineManager()
    manager.initialize_engines()

    # Preprocess
    preprocessed = manager.preprocess_image(test_image_bgr)

    # Recognize
    result = manager.recognize_text(preprocessed)

    print(f"✓ OcrEngineManager result:")
    print(f"  Text: '{result.text}'")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Engine: {result.engine_used}")

except Exception as e:
    print(f"✗ OcrEngineManager failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("Done!")
