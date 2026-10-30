import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
try:
    from mp_path_fix import fix_windows_unicode_path
    fix_windows_unicode_path(__file__)
except ImportError:
    pass
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import math
import urllib.request
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]
def draw_hand_landmarks(frame, landmarks, img_w, img_h, connections=HAND_CONNECTIONS):
    points = []
    for lm in landmarks:
        px = int(lm.x * img_w)
        py = int(lm.y * img_h)
        points.append((px, py))
        cv2.circle(frame, (px, py), 3, (0, 0, 255), -1)

    for start, end in connections:
        if start < len(points) and end < len(points):
            cv2.line(frame, points[start], points[end], (0, 255, 0), 2)

img = cv2.imread(r"C:\Picture\hoa.webp")
if img is None:
    print("[LOI] Khong tim thay anh, vui lòng kiem tra lai duong dan!")
    sys.exit(1)

img_h, img_w = img.shape[:2]

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
if not os.path.exists(MODEL_PATH):
    print("[INFO] Dang tai model HandLandmarker (~10MB)...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[INFO] Tai model thanh cong:", MODEL_PATH)
    except Exception as e:
        print("[LOI] Khong the tai model:", e)
        sys.exit(1)

base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=1,
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.7,
    min_tracking_confidence=0.7
)
detector = vision.HandLandmarker.create_from_options(options)

vid = cv2.VideoCapture(0)
zoom = 2.0
offset_x = 0.0
offset_y = 0.0
prev_x = None
prev_y = None
alpha = 0.3
sensitivity = 2.0

print("=== ĐANG CHẠY NHIỆM VỤ 2: PAN ẢNH BẰNG NGÓN TRỎ ===")
print("Hướng dẫn: Dùng ngón trỏ di chuyển qua lại/lên xuống để trượt ảnh. Nhấn 'q' để thoát.")

while True:
    ret, frame = vid.read()
    if not ret:
        break
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    
    result = detector.detect(mp_image)
    if result.hand_landmarks and len(result.hand_landmarks) > 0:
        landmarks = result.hand_landmarks[0]
        index_tip = landmarks[8]
        finger_x = index_tip.x * w
        finger_y = index_tip.y * h
        if prev_x is None or prev_y is None:
            prev_x, prev_y = float(finger_x), float(finger_y)
        smooth_x = alpha * finger_x + (1 - alpha) * prev_x
        smooth_y = alpha * finger_y + (1 - alpha) * prev_y
        dx = (smooth_x - prev_x) * sensitivity
        dy = (smooth_y - prev_y) * sensitivity

        prev_x, prev_y = smooth_x, smooth_y

        offset_x -= dx
        offset_y -= dy

        cv2.circle(frame, (int(finger_x), int(finger_y)), 10, (0, 255, 0), -1)
        draw_hand_landmarks(frame, landmarks, w, h)
    else:

        prev_x, prev_y = None, None

    new_w = max(1, int(img_w / zoom))
    new_h = max(1, int(img_h / zoom))

    max_offset_x = float(img_w - new_w)
    max_offset_y = float(img_h - new_h)

    offset_x = max(0.0, min(offset_x, max_offset_x))
    offset_y = max(0.0, min(offset_y, max_offset_y))

    x_start = int(offset_x)
    y_start = int(offset_y)
    
    crop = img[y_start:y_start + new_h, x_start:x_start + new_w]
    zoomed_img = cv2.resize(crop, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
    cv2.putText(zoomed_img, f"Zoom: {zoom:.1f}x | Offset X: {int(offset_x)} Y: {int(offset_y)}", 
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow("Webcam - Tracking", frame)
    cv2.imshow("Nhiem Vu 2 - Pan Anh", zoomed_img)

    key = cv2.waitKey(20) & 0xFF
    if key == ord("q"):
        break

vid.release()
detector.close()
cv2.destroyAllWindows()