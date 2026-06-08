import cv2
import numpy as np
import requests
import time
from ultralytics import YOLO

ESP_IP = "172.20.10.3"
CAMERA_URL    = f"http://{ESP_IP}/jpg"
CAR_URL       = f"http://{ESP_IP}/car"
FLASH_ON_URL  = f"http://{ESP_IP}/flash/on"
FLASH_OFF_URL = f"http://{ESP_IP}/flash/off"

CONFIDENCE    = 0.5
PERSISTENCE_FRAMES = 3
DARK_THRESHOLD = 60
BRIGHTNESS_CHECK_INTERVAL = 30
FLASH_TOGGLE_COOLDOWN = 3.0

print("Loading YOLO model...")
model = YOLO("yolov8n.pt")
print("Model loaded")

active_ids = {}
fired_ids = set()
car_count = 0
frame_counter = 0
flash_state = None
last_flash_toggle = 0

def set_flash(on):
    global flash_state, last_flash_toggle
    now = time.time()
    if flash_state == on: return
    if now - last_flash_toggle < FLASH_TOGGLE_COOLDOWN: return
    try:
        requests.get(FLASH_ON_URL if on else FLASH_OFF_URL, timeout=1)
        flash_state = on
        last_flash_toggle = now
        print(f"Flash {'ON' if on else 'OFF'}")
    except: pass

def send_car():
    try:
        requests.get(CAR_URL, timeout=1)
    except: pass

print("Detection running. Press Q to quit.")

while True:
    try:
        response = requests.get(CAMERA_URL, timeout=2)
        img_array = np.frombuffer(response.content, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None: continue

        frame_counter += 1
        if frame_counter % BRIGHTNESS_CHECK_INTERVAL == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if int(np.mean(gray)) < DARK_THRESHOLD:
                set_flash(True)
            else:
                set_flash(False)

        results = model.track(frame, persist=True, conf=CONFIDENCE,
                              verbose=False, tracker="bytetrack.yaml")

        this_frame_ids = set()
        if results[0].boxes.id is not None:
            this_frame_ids = set(results[0].boxes.id.int().cpu().tolist())

        for obj_id in this_frame_ids:
            active_ids[obj_id] = 0
            if obj_id not in fired_ids:
                car_count += 1
                print(f"NEW CAR (ID #{obj_id}) - Total: {car_count}")
                send_car()
                fired_ids.add(obj_id)

        for obj_id in list(active_ids.keys()):
            if obj_id not in this_frame_ids:
                active_ids[obj_id] += 1
                if active_ids[obj_id] > PERSISTENCE_FRAMES:
                    del active_ids[obj_id]

        annotated = results[0].plot()
        cv2.putText(annotated, f"Cars: {car_count}", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        cv2.putText(annotated, f"Active: {len(active_ids)}", (10,60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,200,255), 2)
        cv2.imshow("Smart Street Light - AI Detection", annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    except requests.exceptions.RequestException:
        time.sleep(0.3)
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(0.3)

cv2.destroyAllWindows()
