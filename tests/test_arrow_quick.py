"""
Quick Arrow Detection Test Script
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import cv2
import numpy as np

print("Testing Arrow Detector...")
print("=" * 50)

try:
    from services.arrow_detector import ArrowDetector
    print("OK - ArrowDetector imported")

    detector = ArrowDetector()
    print(f"OK - Loaded {len(detector.templates)} arrow types")

    for arrow_type, templates_list in detector.templates.items():
        print(f"  {arrow_type}: {len(templates_list)} templates")

    # Create a test image
    test_img = np.ones((50, 50, 3), dtype=np.uint8) * 255

    # Test detection
    result = detector.detect_arrow(test_img, (0, 0, 50, 50))
    print(f"\nTest detection result:")
    print(f"  Direction: {result.direction}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Template matched: {result.template_matched}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
