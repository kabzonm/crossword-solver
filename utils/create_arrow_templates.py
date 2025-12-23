"""
Arrow Template Generator
יוצר תבניות חצים באופן פרוגרמטי
"""

import cv2
import numpy as np
import os


def create_straight_arrow(size, direction):
    """יצירת חץ ישר"""
    img = np.ones((size, size, 3), dtype=np.uint8) * 255
    center = size // 2
    arrow_len = int(size * 0.6)
    arrow_thick = max(2, size // 15)
    arrow_head = max(3, size // 10)

    if direction == 'left':
        # קו ראשי
        cv2.line(img, (size - 5, center), (5, center), (0, 0, 0), arrow_thick)
        # ראש חץ
        cv2.line(img, (5, center), (5 + arrow_head, center - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, (5, center), (5 + arrow_head, center + arrow_head), (0, 0, 0), arrow_thick)

    elif direction == 'right':
        cv2.line(img, (5, center), (size - 5, center), (0, 0, 0), arrow_thick)
        cv2.line(img, (size - 5, center), (size - 5 - arrow_head, center - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, (size - 5, center), (size - 5 - arrow_head, center + arrow_head), (0, 0, 0), arrow_thick)

    elif direction == 'down':
        cv2.line(img, (center, 5), (center, size - 5), (0, 0, 0), arrow_thick)
        cv2.line(img, (center, size - 5), (center - arrow_head, size - 5 - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, (center, size - 5), (center + arrow_head, size - 5 - arrow_head), (0, 0, 0), arrow_thick)

    elif direction == 'up':
        cv2.line(img, (center, size - 5), (center, 5), (0, 0, 0), arrow_thick)
        cv2.line(img, (center, 5), (center - arrow_head, 5 + arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, (center, 5), (center + arrow_head, 5 + arrow_head), (0, 0, 0), arrow_thick)

    return img


def create_step_arrow(size, start_dir, turn_dir):
    """יצירת חץ מדרגות (L-shape)"""
    img = np.ones((size, size, 3), dtype=np.uint8) * 255
    center = size // 2
    arrow_thick = max(2, size // 15)
    arrow_head = max(3, size // 10)
    step_len = int(size * 0.3)

    # נקודות המפתח
    if start_dir == 'up' and turn_dir == 'right':
        # מתחיל למעלה ופונה ימינה
        p1 = (center, size - 5)
        p2 = (center, center)
        p3 = (size - 5, center)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)

    elif start_dir == 'up' and turn_dir == 'left':
        p1 = (center, size - 5)
        p2 = (center, center)
        p3 = (5, center)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)

    elif start_dir == 'down' and turn_dir == 'right':
        p1 = (center, 5)
        p2 = (center, center)
        p3 = (size - 5, center)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)

    elif start_dir == 'down' and turn_dir == 'left':
        p1 = (center, 5)
        p2 = (center, center)
        p3 = (5, center)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)

    elif start_dir == 'left' and turn_dir == 'down':
        p1 = (size - 5, center)
        p2 = (center, center)
        p3 = (center, size - 5)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)

    elif start_dir == 'left' and turn_dir == 'up':
        p1 = (size - 5, center)
        p2 = (center, center)
        p3 = (center, 5)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)

    elif start_dir == 'right' and turn_dir == 'down':
        p1 = (5, center)
        p2 = (center, center)
        p3 = (center, size - 5)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] - arrow_head), (0, 0, 0), arrow_thick)

    elif start_dir == 'right' and turn_dir == 'up':
        p1 = (5, center)
        p2 = (center, center)
        p3 = (center, 5)
        cv2.line(img, p1, p2, (0, 0, 0), arrow_thick)
        cv2.line(img, p2, p3, (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] - arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)
        cv2.line(img, p3, (p3[0] + arrow_head, p3[1] + arrow_head), (0, 0, 0), arrow_thick)

    return img


def generate_all_templates(output_dir):
    """יוצר את כל 36 התבניות"""
    os.makedirs(output_dir, exist_ok=True)

    sizes = {
        'small': 20,
        'medium': 30,
        'large': 40
    }

    # חצים ישרים
    straight_arrows = ['left', 'right', 'down', 'up']
    for direction in straight_arrows:
        for size_name, size_px in sizes.items():
            img = create_straight_arrow(size_px, direction)
            filename = f"straight_{direction}_{size_name}.png"
            cv2.imwrite(os.path.join(output_dir, filename), img)
            print(f"Created: {filename}")

    # חצי מדרגות
    step_arrows = [
        ('up', 'right'),
        ('up', 'left'),
        ('down', 'right'),
        ('down', 'left'),
        ('left', 'down'),
        ('left', 'up'),
        ('right', 'down'),
        ('right', 'up'),
    ]

    for start_dir, turn_dir in step_arrows:
        for size_name, size_px in sizes.items():
            img = create_step_arrow(size_px, start_dir, turn_dir)
            filename = f"start_{start_dir}_turn_{turn_dir}_{size_name}.png"
            cv2.imwrite(os.path.join(output_dir, filename), img)
            print(f"Created: {filename}")

    print(f"\n✅ Successfully created all 36 arrow templates in {output_dir}")


if __name__ == "__main__":
    # הרצה ישירה
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, 'assets', 'arrow_templates')
    generate_all_templates(templates_dir)
