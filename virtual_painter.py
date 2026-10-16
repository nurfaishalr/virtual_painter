import cv2
import mediapipe as mp
import numpy as np
import math

# MEDIAPIPE
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.5
)

# CAMERA DETECTION
def open_camera():
    # Prioritas kamera eksternal
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    return cap

cap = open_camera()

if cap is None:
    print("Tidak ada kamera ditemukan!")
    exit()

print("Resolution:", int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "x", int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

# WINDOW
window_name = "Virtual Painter"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1600, 900)
cv2.moveWindow(window_name, 100, 50)
try:
    cv2.setWindowProperty(window_name, cv2.WND_PROP_MAXIMIZED, cv2.WINDOW_MAXIMIZED)
except:
    pass

# DRAW SETTINGS
brush_color = (0, 0, 255)
brush_thickness = 5
eraser_size = 50
canvas = None
prev_x = None
prev_y = None
pinch_frames = 0
peace_frames = 0

# HELPER
def distance(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def pinch_ratio(landmarks, w, h):
    thumb_tip = (int(landmarks[4].x * w), int(landmarks[4].y * h))
    index_tip = (int(landmarks[8].x * w), int(landmarks[8].y * h))
    wrist = (int(landmarks[0].x * w), int(landmarks[0].y * h))
    middle_tip = (int(landmarks[12].x * w), int(landmarks[12].y * h))
    pinch_dist = distance(thumb_tip, index_tip)
    hand_size = distance(wrist, middle_tip)
    if hand_size == 0:
        return 999
    return pinch_dist / hand_size

def is_fist(landmarks):
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]
    closed = 0
    for tip, pip in zip(finger_tips, finger_pips):
        if landmarks[tip].y > landmarks[pip].y:
            closed += 1
    return closed >= 4

def is_peace(landmarks):
    """
    Telunjuk + jari tengah terbuka
    Jari manis + kelingking tertutup
    """
    index_up = landmarks[8].y < landmarks[6].y
    middle_up = landmarks[12].y < landmarks[10].y
    ring_down = landmarks[16].y > landmarks[14].y
    pinky_down = landmarks[20].y > landmarks[18].y
    return (index_up and middle_up and ring_down and pinky_down)

# MAIN LOOP
while True:
    success, frame = cap.read()
    if not success:
        break
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    if canvas is None:
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)
    mode = "IDLE"
    if results.multi_hand_landmarks:
        hand = results.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)
        lm = hand.landmark
        index_x = int(lm[8].x * w)
        index_y = int(lm[8].y * h)
        ratio = pinch_ratio(lm, w, h)
        pinch = ratio < 0.18
        fist = is_fist(lm)
        peace = is_peace(lm)

        # RESET CANVAS
        if peace:
            peace_frames += 1
            if peace_frames >= 15:
                canvas[:] = 0
                prev_x = None
                prev_y = None
                mode = "RESET"
        else:
            peace_frames = 0

        # ERASER
        if fist:
            mode = "ERASER"
            pinch_frames = 0
            if prev_x is None:
                prev_x = index_x
                prev_y = index_y
            cv2.line(canvas, (prev_x, prev_y), (index_x, index_y), (0, 0, 0), eraser_size)
            cv2.circle(frame, (index_x, index_y), eraser_size // 2, (255, 0, 0), 2)
            prev_x = index_x
            prev_y = index_y

        # DRAW
        elif pinch and not peace:
            pinch_frames += 1
            if pinch_frames >= 3:
                mode = "DRAW"
                if prev_x is None:
                    prev_x = index_x
                    prev_y = index_y
                smooth_x = int(prev_x * 0.7 + index_x * 0.3)
                smooth_y = int(prev_y * 0.7 + index_y * 0.3)
                cv2.line(canvas, (prev_x, prev_y), (smooth_x, smooth_y), brush_color, brush_thickness)
                cv2.circle(frame, (index_x, index_y), 10, (0, 255, 0), -1)
                prev_x = smooth_x
                prev_y = smooth_y

        # IDLE
        elif not fist and not peace:
            pinch_frames = 0
            prev_x = None
            prev_y = None
            mode = "IDLE"
    else:
        pinch_frames = 0
        peace_frames = 0
        prev_x = None
        prev_y = None

    # MODE
    cv2.putText(frame, f"MODE: {mode}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    # MERGE CANVAS
    gray_canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray_canvas, 20, 255, cv2.THRESH_BINARY)
    mask_inv = cv2.bitwise_not(mask)
    frame_bg = cv2.bitwise_and(frame, frame, mask = mask_inv)
    canvas_fg = cv2.bitwise_and(canvas, canvas, mask=mask)
    output = cv2.add(frame_bg, canvas_fg)
    cv2.imshow(window_name, output)
    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break
    if key == ord("q"):
        break
    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break

# CLEANUP
cap.release()
cv2.destroyAllWindows()