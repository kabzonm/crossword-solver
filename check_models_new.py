import os
from google import genai

# --- המפתח שלך ---
os.environ["GOOGLE_API_KEY"] = "AIzaSyCFaQeZyVQ2YaOdBnMaNSMHslNxKp1gz-A" # שים כאן את המפתח האמיתי שלך

def list_models_simple():
    print("--- בודק מודלים זמינים... ---")
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        
        # שליפת כל המודלים
        for model in client.models.list():
            # בספרייה החדשה, השם נמצא פשוט תחת .name
            print(f"מודל נמצא: {model.name}")
            
    except Exception as e:
        print(f"שגיאה: {e}")

if __name__ == "__main__":
    list_models_simple()