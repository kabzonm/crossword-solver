"""
Quick import test to verify all dependencies are working
"""
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing imports...")

try:
    import streamlit as st
    print("[OK] Streamlit")
except Exception as e:
    print(f"[FAIL] Streamlit: {e}")

try:
    import cv2
    print("[OK] OpenCV")
except Exception as e:
    print(f"[FAIL] OpenCV: {e}")

try:
    import numpy as np
    print("[OK] NumPy")
except Exception as e:
    print(f"[FAIL] NumPy: {e}")

try:
    from PIL import Image
    print("[OK] PIL")
except Exception as e:
    print(f"[FAIL] PIL: {e}")

try:
    from streamlit_drawable_canvas import st_canvas
    print("[OK] Drawable Canvas")
except Exception as e:
    print(f"[FAIL] Drawable Canvas: {e}")

try:
    from services.vision_service import VisionService
    print("[OK] VisionService")
except Exception as e:
    print(f"[FAIL] VisionService: {e}")

try:
    from services.ocr_service_new import OcrService
    print("[OK] OcrService (new)")
except Exception as e:
    print(f"[FAIL] OcrService (new): {e}")

try:
    from models.grid import CellType
    print("[OK] Grid Model")
except Exception as e:
    print(f"[FAIL] Grid Model: {e}")

print("\nAll core imports successful!")
print("\nNOTE: OCR engines (EasyOCR/PaddleOCR) are NOT tested here.")
print("They will be loaded lazily when needed.")
