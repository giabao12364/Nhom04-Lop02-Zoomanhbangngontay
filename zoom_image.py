import sys
import os
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
from mp_path_fix import fix_windows_unicode_path
fix_windows_unicode_path(__file__)

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
# ==============================
# NGUOI 3: NHAN DIEN CU CHI TAY(NAM)
# ==============================

def classify_gesture(landmarks):
    """
    Phan loai cu chi ban tay dua tren 21 landmark MediaPipe.

    Tra ve:
        RESET: Ban tay xoe
        PAUSE: Ban tay nam
        NONE: Cu chi khong hop le
    """

    # Kiem tra landmark
    if landmarks is None or len(landmarks) != 21:
        return "NONE"

    # Kiem tra cac ngon tay co dang gap hay khong
    # Ngon tro, giua, ap ut, ut
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]

    fingers_up = []

    for tip, pip in zip(finger_tips, finger_pips):

        # Toa do y nho hon nghia la ngon tay dang huong len
        if landmarks[tip].y < landmarks[pip].y:
            fingers_up.append(1)
        else:
            fingers_up.append(0)

    # Xoe ban tay: ca 4 ngon tay deu huong len
    if fingers_up == [1, 1, 1, 1]:
        return "RESET"

    # Nam ban tay: ca 4 ngon tay deu gap
    if fingers_up == [0, 0, 0, 0]:
        return "PAUSE"

    # Cac truong hop khac
    return "NONE"

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
zoom = 1.0

# NGUOI 3: Trang thai dieu khien(NAM)
paused = False

# Bien xu ly cu chi lap lai
gesture_candidate = "NONE"
gesture_count = 0
gesture_latched = False

# So khung hinh xac nhan cu chi
GESTURE_THRESHOLD = 8

while True:
    ret, frame = vid.read()
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = detector.detect(mp_image)
    if result.hand_landmarks and len(result.hand_landmarks) > 0:
        landmarks = result.hand_landmarks[0]
        
            # NGUOI 3: XU LY CU CHI VA CHONG LAP(NAM)
            gesture = classify_gesture(landmarks)

            # Dem so khung hinh lien tiep cua cu chi
            if gesture == gesture_candidate:
                gesture_count += 1
            else:
                gesture_candidate = gesture
                gesture_count = 1

            # Chi xu ly khi cu chi du on dinh
            if gesture_count >= GESTURE_THRESHOLD:

                # RESET: Dua anh ve trang thai ban dau
                if gesture == "RESET" and not gesture_latched:
                    zoom = 1.0
                    paused = False
                    gesture_latched = True

                # PAUSE: Tam dung / tiep tuc dieu khien
                elif gesture == "PAUSE" and not gesture_latched:
                    paused = not paused
                    gesture_latched = True

                # NONE: Cho phep nhan dien cu chi moi
                elif gesture == "NONE":
                    gesture_latched = False
            
        thumb = landmarks[4]
        index = landmarks[8]
        x1 = int(thumb.x * w)
        y1 = int(thumb.y * h)
        x2 = int(index.x * w)
        y2 = int(index.y * h)
    # Chi cap nhat zoom khi khong tam dung(NAM)
    if not paused:
        distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        
        zoom = 1.0 + distance / 150
        zoom = max(1.0, min(zoom, 4.0))
        cv2.circle(frame, (x1, y1), 10, (255, 0, 0), -1)
        cv2.circle(frame, (x2, y2), 10, (0, 255, 0), -1)
        cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 0), 3)
        draw_hand_landmarks(frame, landmarks, w, h)
        # NGUOI 3: ZOOM THEO VI TRI NGON TRO(NAM)
        img_h, img_w = img.shape[:2]

        new_w = max(1, int(img_w / zoom))
        new_h = max(1, int(img_h / zoom))

        # Lay ngon tro lam tam vung crop
        x_start = int(x2 - new_w / 2)
        y_start = int(y2 - new_h / 2)

        # Gioi han vung crop trong anh goc
        x_start = max(0, min(x_start, img_w - new_w))
        y_start = max(0, min(y_start, img_h - new_h))
    
    crop = img[y_start:y_start + new_h, x_start:x_start + new_w]
    zoomed_img = cv2.resize(crop, (img_w, img_h))
    cv2.putText(zoomed_img, "Zoom: {:.2f}x".format(zoom), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        # Hien thi trang thai dieu khien(NAM)
    if paused:
            cv2.putText(
                zoomed_img,
                "PAUSED",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )
    cv2.imshow("Image", zoomed_img)
    cv2.imshow("Webcam", frame)
    key = cv2.waitKey(20) & 0xFF
    if key == ord("q"): break
vid.release()
cv2.destroyAllWindows()
