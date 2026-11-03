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
from collections import deque
from zoom_log import ZoomLogger, plot_log

ZOOM_SMOOTHING = 0.2
ZOOM_MIN = 1.0
ZOOM_MAX = 4.0
PALM_RATIO_MAX = 1.2
HAND_LOST_TIMEOUT = 10
ZOOM_DEAD_ZONE = 0.02
LOG_ZOOM = True
SMOOTH_MODE = "ema"         
FPS_ASSUMED = 30.0
ONE_EURO_MIN_CUTOFF = 1.5
ONE_EURO_BETA = 0.02
ONE_EURO_D_CUTOFF = 1.0
RATIO_MEDIAN_WINDOW = 5    
ZOOM_MAX_STEP = 0.08         
DETECT_WIDTH = 640           
SHARPEN = True               

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
def median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]
def one_euro_alpha(cutoff, dt):
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)
def one_euro_step(x, x_hat, dx_hat, dt):
    dx = (x - x_hat) / dt
    dx_hat = dx_hat + one_euro_alpha(ONE_EURO_D_CUTOFF, dt) * (dx - dx_hat)
    cutoff = ONE_EURO_MIN_CUTOFF + ONE_EURO_BETA * abs(dx_hat)
    x_hat = x_hat + one_euro_alpha(cutoff, dt) * (x - x_hat)
    return x_hat, dx_hat
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
def run_zoom(img, cam_index=0):
    if img is None:
        print("[LOI] Anh dau vao khong hop le.")
        return
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
    vid = cv2.VideoCapture(cam_index)
    if not vid.isOpened():
        print("[LOI] Khong the mo webcam:", cam_index)
        detector.close()
        return
    zoom = 1.0
    smooth_zoom = 1.0
    hand_lost_frames = 0
    logger = ZoomLogger() if LOG_ZOOM else None
    ratio_history = deque(maxlen=RATIO_MEDIAN_WINDOW)
    x_hat = ZOOM_MIN
    dx_hat = 0.0
    ratio_max = 0.0
    while True:
        ret, frame = vid.read()
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        if w > DETECT_WIDTH:
            detect_frame = cv2.resize(frame, (DETECT_WIDTH, int(h * DETECT_WIDTH / w)))
        else:
            detect_frame = frame
        rgb = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect(mp_image)
        if result.hand_landmarks and len(result.hand_landmarks) > 0:
            hand_lost_frames = 0
            landmarks = result.hand_landmarks[0]
            thumb = landmarks[4]
            index = landmarks[8]
            x1 = int(thumb.x * w)
            y1 = int(thumb.y * h)
            x2 = int(index.x * w)
            y2 = int(index.y * h)
            distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            palm_dx = (landmarks[9].x - landmarks[0].x) * w
            palm_dy = (landmarks[9].y - landmarks[0].y) * h
            palm = math.sqrt(palm_dx ** 2 + palm_dy ** 2)
            if palm > 1e-6:
                ratio = distance / palm
                if ratio > ratio_max:
                    ratio_max = ratio
                ratio_history.append(ratio)
                ratio_filtered = median(ratio_history)
                zoom = ZOOM_MIN + (ratio_filtered / PALM_RATIO_MAX) * (ZOOM_MAX - ZOOM_MIN)
                zoom = max(ZOOM_MIN, min(zoom, ZOOM_MAX))
                if abs(zoom - smooth_zoom) > ZOOM_DEAD_ZONE:
                    if SMOOTH_MODE == "one_euro":
                        target, dx_hat = one_euro_step(zoom, x_hat, dx_hat, 1.0 / FPS_ASSUMED)
                    else:
                        target = smooth_zoom + ZOOM_SMOOTHING * (zoom - smooth_zoom)
                    x_hat = target
                    step = max(-ZOOM_MAX_STEP, min(target - smooth_zoom, ZOOM_MAX_STEP))
                    smooth_zoom = smooth_zoom + step
                if logger is not None:
                    logger.log(ratio, zoom, smooth_zoom)
            cv2.circle(frame, (x1, y1), 10, (255, 0, 0), -1)
            cv2.circle(frame, (x2, y2), 10, (0, 255, 0), -1)
            cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 0), 3)
            draw_hand_landmarks(frame, landmarks, w, h)
        else:
            hand_lost_frames += 1
            if hand_lost_frames > HAND_LOST_TIMEOUT:
                smooth_zoom = smooth_zoom + ZOOM_SMOOTHING * (ZOOM_MIN - smooth_zoom)
        img_h, img_w = img.shape[:2]
        new_w = max(1, int(img_w / smooth_zoom))
        new_h = max(1, int(img_h / smooth_zoom))
        x_start = (img_w - new_w) // 2
        y_start = (img_h - new_h) // 2
        crop = img[y_start:y_start + new_h, x_start:x_start + new_w]
        if crop.size>0:
            if smooth_zoom > 1.2:
                zoomed_img = cv2.resize(crop, (img_w, img_h), interpolation=cv2.INTER_CUBIC)
            else:
                zoomed_img = cv2.resize(crop, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
            if SHARPEN and smooth_zoom > 1.2:
                blur = cv2.GaussianBlur(zoomed_img, (0, 0), 3)
                zoomed_img = cv2.addWeighted(zoomed_img, 1.5, blur, -0.5, 0)
        else:
            zoomed_img=img.copy()
        cv2.putText(zoomed_img, "Zoom: {:.2f}x".format(smooth_zoom), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Image", zoomed_img)
        cv2.imshow("Webcam", frame)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q"): break
    vid.release()
    detector.close()
    cv2.destroyAllWindows()
    if logger is not None:
        csv_path = logger.save_csv()
        print("[LOG] Da luu du lieu zoom:", csv_path)
        png_path = plot_log(csv_path)
        if png_path is not None:
            print("[LOG] Da ve bieu do so sanh:", png_path)
    if ratio_max > 0:
        print("[GOI Y] ratio lon nhat do duoc: {:.2f} (dat PALM_RATIO_MAX gan gia tri nay de dung het dai zoom)".format(ratio_max))
if __name__ == "__main__":
    default_img = cv2.imread(r"C:\Picture\hoa.webp")
    run_zoom(default_img, 0)
