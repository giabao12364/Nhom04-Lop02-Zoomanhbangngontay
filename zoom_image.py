import sys
import os

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

# [NOTE - SỬA CODE GỐC]: Bọc try-except để nếu máy khác chạy thiếu file mp_path_fix.py thì không bị crash ngay
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


# ==============================================================================
# NGUOI 3: PHAN LOAI CU CHI BAN TAY
# ==============================================================================
def classify_gesture(landmarks):
    """
    Phan loai cu chi:
      - RESET: Xoe 4 ngon tay (tro, giua, ap ut, ut)
      - PAUSE: Nam chat 4 ngon tay
      - NONE : Cac cu chi khac (chum 2 ngon de zoom)
    """
    if landmarks is None or len(landmarks) != 21:
        return "NONE"

    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]
    fingers_up = []

    for tip, pip in zip(finger_tips, finger_pips):
        # Y nho hon nghia la dau ngon tay huong len tren
        if landmarks[tip].y < landmarks[pip].y:
            fingers_up.append(1)
        else:
            fingers_up.append(0)

    if fingers_up == [1, 1, 1, 1]:
        return "RESET"
    if fingers_up == [0, 0, 0, 0]:
        return "PAUSE"
    return "NONE"


img = cv2.imread(r"C:\Picture\hoa.webp")

# [NOTE - SỬA CODE GỐC]: Kiem tra anh ton tai, tranh crash loi NoneType o img.shape
if img is None:
    print("[LOI] Khong the doc anh. Hay kiem tra lai duong dan C:\\Picture\\hoa.webp")
    sys.exit(1)

# [NOTE - SỬA CODE GỐC]: Dua img_h, img_w ra ngoai de khong bi doc lai trong while gay cham
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

# [NOTE - SỬA CODE GỐC]: Kiem tra mo webcam thanh cong truoc khi doc frame
if not vid.isOpened():
    print("[LOI] Khong the mo webcam.")
    detector.close()
    sys.exit(1)

zoom = 1.0

# ==============================================================================
# NGUOI 3: BIEN QUAN LY TRANG THAI VA TOA DO
# ==============================================================================
paused = False
gesture_candidate = "NONE"
gesture_count = 0
gesture_latched = False
GESTURE_THRESHOLD = 8  # So frame can on dinh de xac nhan cu chi

# Toa do tam crop ban dau (mac dinh o giua anh)
center_x = img_w // 2
center_y = img_h // 2

while True:
    ret, frame = vid.read()

    # [NOTE - SỬA CODE GỐC]: Kiem tra ret tranh loi khi ngat camera dot ngot
    if not ret or frame is None:
        print("[LOI] Mat tin hieu webcam.")
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = detector.detect(mp_image)

    if result.hand_landmarks and len(result.hand_landmarks) > 0:
        landmarks = result.hand_landmarks[0]

        # ==============================================================================
        # NGUOI 3: XU LY NHAN DIEN CU CHI VA CHONG KET TRANG THAI
        # ==============================================================================
        gesture = classify_gesture(landmarks)

        if gesture == gesture_candidate:
            gesture_count += 1
        else:
            gesture_candidate = gesture
            gesture_count = 1
            gesture_latched = False  # Reset chot ngay khi doi cu chi (tranh bi ket trang thai)

        # Kich hoat khi cu chi da on dinh du so khung hinh
        if gesture_count >= GESTURE_THRESHOLD and not gesture_latched:
            if gesture == "RESET":
                zoom = 1.0
                paused = False
                center_x, center_y = img_w // 2, img_h // 2
                gesture_latched = True
            elif gesture == "PAUSE":
                paused = not paused
                gesture_latched = True

        thumb = landmarks[4]
        index = landmarks[8]

        x1 = int(thumb.x * w)
        y1 = int(thumb.y * h)
        x2 = int(index.x * w)
        y2 = int(index.y * h)

        # ==============================================================================
        # NGUOI 3: CAP NHAT ZOOM VA QUY DOI TOA DO CHUAN CHO ANH GOC
        # ==============================================================================
        if gesture == "RESET":
            zoom = 1.0
        elif not paused:
            # Quy doi toa do ngon tro theo ti le sang he anh goc (tranh lech do phan giai)
            center_x = int(index.x * img_w)
            center_y = int(index.y * img_h)

            # Tinh khoang cach 2 ngon de zoom
            distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            zoom = 1.0 + distance / 150
            zoom = max(1.0, min(zoom, 4.0))

        cv2.circle(frame, (x1, y1), 10, (255, 0, 0), -1)
        cv2.circle(frame, (x2, y2), 10, (0, 255, 0), -1)
        cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 0), 3)
        draw_hand_landmarks(frame, landmarks, w, h)

    # ==============================================================================
    # NGUOI 3: CROP ANH THEO TOA DO NGON TRO (center_x, center_y) CO CHAN BIEN
    # ==============================================================================
    new_w = max(1, int(img_w / zoom))
    new_h = max(1, int(img_h / zoom))

    # Tinh toa do bat dau vung crop xung quanh tam ngon tro
    x_start = int(center_x - new_w // 2)
    y_start = int(center_y - new_h // 2)

    # Chan bien khong cho vung crop vuot khoi khung anh goc
    x_start = max(0, min(x_start, img_w - new_w))
    y_start = max(0, min(y_start, img_h - new_h))

    crop = img[y_start:y_start + new_h, x_start:x_start + new_w]
    zoomed_img = cv2.resize(crop, (img_w, img_h))

    cv2.putText(zoomed_img, "Zoom: {:.2f}x".format(zoom), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Hien thi trang thai PAUSED khi dang tam dung
    if paused:
        cv2.putText(zoomed_img, "PAUSED", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    cv2.imshow("Image", zoomed_img)
    cv2.imshow("Webcam", frame)

    key = cv2.waitKey(20) & 0xFF
    if key == ord("q"):
        break

vid.release()
# [NOTE - SỬA CODE GỐC]: Dong detector de giai phong RAM va model MediaPipe sau khi chay xong
detector.close()
cv2.destroyAllWindows()
