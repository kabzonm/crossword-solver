"""
Quick Batch Processor Test
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import cv2
import numpy as np

print("Testing Batch Processor...")
print("=" * 50)

# Create a mock cell image (50x50 with some text-like content)
cell_image = np.ones((50, 50, 3), dtype=np.uint8) * 255

# Add some black text-like shapes
cv2.putText(cell_image, "abc", (5, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
cv2.arrowedLine(cell_image, (25, 45), (25, 10), (0, 0, 0), 2)

cv2.imwrite("test_cell.png", cell_image)
print("Created test cell image: test_cell.png")

# Test the individual components
from services.ocr_engine_manager import OcrEngineManager
from services.arrow_detector import ArrowDetector
from services.confidence_scorer import ConfidenceScorer

print("\n--- OCR Test ---")
ocr_manager = OcrEngineManager()
ocr_manager.initialize_engines()

preprocessed = ocr_manager.preprocess_image(cell_image)
ocr_result = ocr_manager.recognize_text(preprocessed)
print(f"OCR text: '{ocr_result.text}'")
print(f"OCR confidence: {ocr_result.confidence:.2f}")

print("\n--- Arrow Detection Test ---")
arrow_detector = ArrowDetector()
arrow_result = arrow_detector.detect_arrow(cell_image, (0, 0, 50, 50))
print(f"Arrow direction: {arrow_result.direction}")
print(f"Arrow confidence: {arrow_result.confidence:.2f}")

print("\n--- Confidence Scoring Test ---")
confidence_scorer = ConfidenceScorer()
confidence = confidence_scorer.calculate_confidence(ocr_result, arrow_result, cell_image)
print(f"Overall confidence: {confidence.overall:.2f}")
print(f"Confidence level: {confidence.level}")

print("\n--- Full CellRecognitionResult ---")
from models.recognition_result import CellRecognitionResult

result = CellRecognitionResult(
    ocr_result=ocr_result,
    arrow_result=arrow_result,
    confidence=confidence,
    processing_time=0.5,
    cell_image=cell_image
)

print(f"result.ocr_result exists: {result.ocr_result is not None}")
print(f"result.arrow_result exists: {result.arrow_result is not None}")
print(f"result.confidence exists: {result.confidence is not None}")

# Now test what _update_grid_with_results would extract
ocr_text = result.ocr_result.text if result.ocr_result else ""
ocr_conf = result.ocr_result.confidence if result.ocr_result else 0.0
arrow_dir = result.arrow_result.direction if result.arrow_result else 'none'
arrow_conf = result.arrow_result.confidence if result.arrow_result else 0.0
overall_conf = result.confidence.overall if result.confidence else 0.0

print(f"\nExtracted values for parsed_clues:")
print(f"  text: '{ocr_text}'")
print(f"  path: '{arrow_dir}'")
print(f"  confidence: {overall_conf:.2f}")
print(f"  ocr_confidence: {ocr_conf:.2f}")
print(f"  arrow_confidence: {arrow_conf:.2f}")

print("\n" + "=" * 50)
print("Done!")
