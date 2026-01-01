"""
בדיקת Claude Arrow Detection
"""
import cv2
import numpy as np
import base64
import json

def test_claude_arrow_detection():
    """בדיקת זיהוי חצים עם Claude"""
    print("=" * 60)
    print("Testing Claude Arrow Detection")
    print("=" * 60)

    # טעינת API key
    try:
        with open('claude_api.txt', 'r') as f:
            api_key = f.read().strip().strip('"\'')
        print(f"[OK] API Key loaded: {api_key[:20]}...")
    except FileNotFoundError:
        print("[ERROR] claude_api.txt not found")
        return

    # יצירת תמונת בדיקה עם חץ
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255

    # ציור חץ פשוט למטה
    cv2.arrowedLine(img, (50, 20), (50, 80), (0, 0, 0), 3, tipLength=0.3)

    # המרה ל-base64
    _, buffer = cv2.imencode('.png', img)
    image_base64 = base64.b64encode(buffer).decode('utf-8')

    print(f"[OK] Test image created (100x100 with down arrow)")
    print(f"[OK] Image base64 length: {len(image_base64)}")

    # שליחה ל-Claude
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = """Analyze this Hebrew crossword cell image. Your task is to detect if there's an ARROW in the cell and identify its direction.

IMPORTANT: Look for small arrow symbols that indicate the direction to read/fill the word.

Arrow types:
1. STRAIGHT arrows (single direction):
   - "right": arrow pointing right
   - "left": arrow pointing left
   - "down": arrow pointing down
   - "up": arrow pointing up

2. STEP/L-SHAPED arrows (start in one direction, then turn):
   - "up-right": starts up then turns right
   - "up-left": starts up then turns left
   - "down-right": starts down then turns right
   - "down-left": starts down then turns left
   - "left-down": starts left then turns down
   - "left-up": starts left then turns up
   - "right-down": starts right then turns down
   - "right-up": starts right then turns up

3. "none": NO arrow in the cell (just text or number)

Respond ONLY with JSON:
{"has_arrow": true/false, "direction": "type from list above", "confidence": 0.0-1.0}
"""

        print("\n[...] Sending to Claude API...")

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        response_text = message.content[0].text
        print(f"\n[OK] Claude Response:")
        print("-" * 40)
        print(response_text)
        print("-" * 40)

        # ניסיון לפרסר JSON
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            print(f"\n[OK] Parsed JSON:")
            print(f"  has_arrow: {data.get('has_arrow')}")
            print(f"  direction: {data.get('direction')}")
            print(f"  confidence: {data.get('confidence')}")
        else:
            print("\n[WARNING] Could not find JSON in response")

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_claude_arrow_detection()
