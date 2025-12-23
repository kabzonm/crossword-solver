"""
Arrow Detection Configuration
הגדרות לזיהוי חצים
"""
import os

class ArrowConfig:
    """הגדרות לזיהוי חצים"""

    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TEMPLATES_PATH = os.path.join(BASE_DIR, 'assets', 'arrow_templates')

    # Template matching
    SCALES = [0.8, 1.0, 1.2]  # גדלים שונים לחיפוש
    MATCH_THRESHOLD = 0.6  # סף התאמה מינימלי
    MATCH_METHOD = 'TM_CCOEFF_NORMED'  # שיטת התאמה

    # Arrow types (12 total)
    ARROW_TYPES = [
        # Straight (4)
        'straight-left',
        'straight-right',
        'straight-down',
        'straight-up',

        # Step arrows starting UP (2)
        'start-up-turn-right',
        'start-up-turn-left',

        # Step arrows starting DOWN (2)
        'start-down-turn-right',
        'start-down-turn-left',

        # Step arrows starting LEFT (2)
        'start-left-turn-down',
        'start-left-turn-up',

        # Step arrows starting RIGHT (2)
        'start-right-turn-down',
        'start-right-turn-up',
    ]

    # Template sizes
    TEMPLATE_SIZES = ['small', 'medium', 'large']
    TEMPLATE_SIZE_PX = {
        'small': 20,
        'medium': 30,
        'large': 40
    }

    # Preprocessing
    ADAPTIVE_THRESH_BLOCK_SIZE = 11
    ADAPTIVE_THRESH_C = 2

    # Performance
    ENABLE_CACHING = True
    MAX_CACHE_SIZE = 100
