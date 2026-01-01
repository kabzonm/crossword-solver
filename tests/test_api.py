"""
בדיקת API Keys - Google Vision ו-Claude
"""
import base64
import requests

def test_google_vision():
    """בדיקת Google Vision API"""
    print("=" * 50)
    print("Testing Google Vision API...")
    print("=" * 50)

    # טעינת API key
    try:
        with open('google_vision_api.txt', 'r') as f:
            api_key = f.read().strip()
        print(f"[OK] API Key loaded: {api_key[:20]}...")
    except FileNotFoundError:
        print("[ERROR] google_vision_api.txt not found")
        return False

    # יצירת תמונת בדיקה פשוטה (1x1 pixel)
    import numpy as np
    import cv2

    # תמונה עם טקסט "test"
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    cv2.putText(img, "Test", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    _, buffer = cv2.imencode('.png', img)
    image_base64 = base64.b64encode(buffer).decode('utf-8')

    # שליחת בקשה
    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    request_body = {
        "requests": [{
            "image": {"content": image_base64},
            "features": [{"type": "TEXT_DETECTION", "maxResults": 10}],
            "imageContext": {"languageHints": ["he", "en"]}
        }]
    }

    try:
        response = requests.post(url, json=request_body, timeout=30)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            text = result.get('responses', [{}])[0].get('textAnnotations', [{}])
            if text:
                print(f"[OK] Google Vision working! Detected: '{text[0].get('description', '')}'")
                return True
            else:
                print("[OK] Google Vision working! (no text in test image)")
                return True
        else:
            print(f"[ERROR] {response.status_code}: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return False


def test_claude():
    """בדיקת Claude API"""
    print("\n" + "=" * 50)
    print("Testing Claude API...")
    print("=" * 50)

    # טעינת API key
    try:
        with open('claude_api.txt', 'r') as f:
            api_key = f.read().strip()
            # הסרת גרשיים אם יש
            api_key = api_key.strip('"\'')
        print(f"[OK] API Key loaded: {api_key[:20]}...")
    except FileNotFoundError:
        print("[ERROR] claude_api.txt not found")
        return False

    # בדיקה פשוטה
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": "Say 'API working!' in exactly 2 words."}]
        )

        response_text = message.content[0].text
        print(f"[OK] Claude working! Response: '{response_text}'")
        return True

    except anthropic.AuthenticationError as e:
        print(f"[ERROR] Authentication failed - check your API key")
        print(f"        {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("   API TEST SCRIPT")
    print("=" * 60 + "\n")

    google_ok = test_google_vision()
    claude_ok = test_claude()

    print("\n" + "=" * 60)
    print("   SUMMARY")
    print("=" * 60)
    print(f"Google Vision: {'OK' if google_ok else 'FAILED'}")
    print(f"Claude:        {'OK' if claude_ok else 'FAILED'}")
    print("=" * 60 + "\n")
