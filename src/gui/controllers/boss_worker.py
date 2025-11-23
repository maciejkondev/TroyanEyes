"""
Boss detection worker with YOLOv8.
"""

from PySide6.QtCore import QThread, Signal
import time
import os
import cv2
import numpy as np
from mss import mss
from ultralytics import YOLO

# --- CONFIGURATION ---
# 1. Path to your trained model
# Resolve path relative to this file (src/gui/controllers/boss_worker.py)
# We need to go up to 'src' then down to 'data/weights/model.pt'
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR)) # src/gui/controllers -> src/gui -> src
MODEL_PATH = os.path.join(SRC_DIR, "data", "weights", "model.pt") 

# 2. Region of Interest (ROI) - Adjust these to match your game window
ROI = {
    "top": 150,    # Y coordinate of top-left corner
    "left": 100,    # X coordinate of top-left corner
    "width": 500,  # Width of the map list column 210
    "height": 700  # Height of the map list column 278
}

# 3. Confidence Threshold (Hide weak detections)
CONF_THRESHOLD = 0.30 
# ---------------------

class BossDetectionWorker(QThread):
    """
    Worker thread for YOLO-based boss detection.
    """

    frame_captured = Signal(object) 
    status_changed = Signal(str)
    target_found = Signal()
    target_lost = Signal()
    detection_triggered = Signal(dict)
    stats_updated = Signal(dict)
    channel_switched = Signal(int)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.running = False
        self.paused = False
        self.should_stop = False
        self.last_switch_time = 0.0

    def run(self):
        """Main loop with YOLO inference."""
        self.running = True
        self.status_changed.emit("Worker started")
        
        print(f"Loading model from {MODEL_PATH}...")
        try:
            model = YOLO(MODEL_PATH)
        except Exception as e:
            error_msg = f"Error loading model: {e}"
            print(error_msg)
            self.status_changed.emit(error_msg)
            self.running = False
            return

        # Initialize screen capture
        with mss() as sct:
            print("Starting Preview... Press 'q' to quit.")
            print(f"Model Task: {model.task}")
            print(f"Model Classes: {model.names}")
            self.status_changed.emit("Preview started")
            
            while not self.should_stop:
                if self.paused:
                    time.sleep(0.1)
                    continue

                start_time = time.time()

                # 1. Grab the screen region
                try:
                    screenshot = sct.grab(ROI)
                except Exception as e:
                    print(f"Screen grab failed: {e}")
                    break
                
                # 2. Convert to Numpy array (OpenCV format)
                frame = np.array(screenshot)
                
                # 3. Convert BGRA to BGR (Remove Alpha channel)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # 4. Convert to RGB for YOLO Inference (Model expects RGB)
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

                # 5. Run YOLO Inference
                results = model(frame_rgb, conf=CONF_THRESHOLD, verbose=False)

                # Debug: Analyze results
                r = results[0]
                if r.boxes is not None and len(r.boxes) > 0:
                    print(f"Detections (Boxes): {len(r.boxes)}")
                elif r.probs is not None:
                    print(f"Classification (Probs): {r.probs.top1conf:.2f} (Class: {r.names[r.probs.top1]})")
                else:
                    # No detections
                    pass

                # 6. Visualize Results
                # plot() returns the image in the same format as input (RGB here)
                annotated_frame_rgb = results[0].plot()
                
                # 7. Convert back to BGR for OpenCV display
                annotated_frame = cv2.cvtColor(annotated_frame_rgb, cv2.COLOR_RGB2BGR)

                # 8. Calculate and Draw FPS
                fps = 1.0 / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
                cv2.putText(annotated_frame, f"FPS: {int(fps)}", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                # 9. Show the window
                cv2.imshow("YOLO Live Preview", annotated_frame)

                # 10. Exit logic (check for 'q' key or should_stop)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.should_stop = True
                    break
            
        cv2.destroyAllWindows()
        self.running = False
        self.status_changed.emit("Worker stopped")

    def stop(self):
        self.should_stop = True
        self.wait()

    def pause(self):
        self.paused = True
        self.status_changed.emit("Paused")

    def resume(self):
        self.paused = False
        self.status_changed.emit("Resumed")

    def reset(self):
        self.status_changed.emit("Reset")

    def _switch_to_channel(self, channel_index: int, hotkey_config: dict = None):
        pass

