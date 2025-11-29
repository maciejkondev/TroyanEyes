import os
import cv2
import numpy as np
import mss
import time
from PySide6.QtCore import QThread, Signal, QObject
from ultralytics import YOLO
from game_context import game_context

class BossTabWorker(QThread):
    frame_processed = Signal(np.ndarray)
    status_update = Signal(str)
    
    # Detection settings
    CONF_THRESHOLD = 0.45
    IOU_THRESHOLD = 0.45
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.model = None
        self.load_model()

    def load_model(self):
        try:
            # Path to the boss detector model
            # Assuming it's in the same weights directory as summon_window.pt
            model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'weights', 'boss_detector.pt'))
            
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                self.status_update.emit(f"Model loaded: {os.path.basename(model_path)}")
            else:
                self.status_update.emit(f"Model not found: {model_path}")
                print(f"BossTabWorker: Model not found at {model_path}")
        except Exception as e:
            self.status_update.emit(f"Error loading model: {e}")
            print(f"BossTabWorker: Error loading model: {e}")

    def run(self):
        self.running = True
        self.status_update.emit("Detection started")
        
        while self.running:
            try:
                if not self.model:
                    time.sleep(1)
                    continue

                # Get game window coordinates
                rect = game_context.get_window_rect()
                if not rect:
                    self.status_update.emit("Game window not found")
                    time.sleep(1)
                    continue
                
                left, top, right, bottom = rect
                w = right - left
                h = bottom - top
                
                monitor = {"top": top, "left": left, "width": w, "height": h}
                
                # Capture frame
                with mss.mss() as sct:
                    img = np.array(sct.grab(monitor))
                    
                # Convert to BGR for OpenCV/YOLO
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Run inference
                results = self.model(frame, verbose=False, conf=self.CONF_THRESHOLD, iou=self.IOU_THRESHOLD)
                
                # Annotate frame
                annotated_frame = results[0].plot()
                
                # Emit processed frame for preview
                self.frame_processed.emit(annotated_frame)
                
                # Optional: Process detections logic here (e.g. find closest boss)
                # for box in results[0].boxes:
                #     ...
                
                # Limit FPS to avoid high CPU usage
                time.sleep(0.05) 
                
            except Exception as e:
                print(f"BossTabWorker Error: {e}")
                time.sleep(1)
        
        self.status_update.emit("Detection stopped")

    def stop(self):
        self.running = False
        self.wait()
