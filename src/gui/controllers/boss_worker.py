"""
Boss detection worker - DXCam + GameContext + CPU Optimization.
"""

from PySide6.QtCore import QThread, Signal
import time
import cv2
import numpy as np
import dxcam
import threading
from game_context import game_context
from rapidocr_onnxruntime import RapidOCR
from ultralytics import YOLO
import os
import pyautogui
import Levenshtein

# === CONFIGURATION ===
# ROI is now relative to the game window!
# If the game window is 800x600, this ROI is inside that 800x600.
# === CONFIGURATION ===
# Default ROI (fallback if model detection fails)
RELATIVE_ROI = {
    "top": 150,
    "left": 100,
    "width": 550,
    "height": 300
}

OCR_INTERVAL = 0.35        # Run OCR every 350ms
SCALE_FACTOR = 1.0         # 1.0 = no scaling
ENABLE_CLAHE = True        # Better for dark backgrounds
CLAHE_CLIP_LIMIT = 3.0     
CLAHE_GRID_SIZE = 8        

class BossDetectionWorker(QThread):
    frame_captured = Signal(object)
    status_changed = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.map_priority = config.get("map_priority", [])
        self.click_enabled = config.get("click_enabled", False)
        self.ocr = RapidOCR()
        self.should_stop = False
        self.paused = False
        
        # State Machine
        self.checked_maps = {}  # {map_name: timestamp}
        self.CHECK_COOLDOWN = 10.0  # Seconds before checking the same map again
        self.state = "SCANNING"  # SCANNING, WAITING_FOR_BOSS_LIST, CHECKING_BOSSES
        self.state_timer = 0
        self.current_map_name = None
        self.locked_boss_roi = None
        self.boss_status_change_counter = 0
        
        # Channel Logic
        self.num_channels = config.get("num_channels", 1)
        self.current_channel = 1
        self.channel_switch_time = 0

        # DXCam instance
        self.camera = None

        # OCR state
        self.last_ocr_time = 0
        self.latest_ocr_result = None
        self.ocr_lock = threading.Lock()

        # Performance metrics
        self.last_ocr_fps = 0.0
        self.last_ocr_ms = 0.0
        
        # Pre-initialize CLAHE
        if ENABLE_CLAHE:
            self.clahe = cv2.createCLAHE(
                clipLimit=CLAHE_CLIP_LIMIT,
                tileGridSize=(CLAHE_GRID_SIZE, CLAHE_GRID_SIZE)
            )
        else:
            self.clahe = None

        # Initialize YOLO Model for ROI detection
        self.model = None
        self.detected_roi = None
        self.last_roi_update_time = 0
        self.last_scroll_time = 0
        self.last_scroll_finish_time = 0
        self.last_target_found_time = 0
        self.scroll_count = 0
        self.scroll_direction = 1  # 1 for down, -1 for up
        self.ROI_UPDATE_INTERVAL = 2.0  # Check every 2 seconds

        try:
            # Path relative to this file: ../../data/weights/model.pt
            model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'weights', 'model.pt'))
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                print(f"YOLO model loaded from: {model_path}")
            else:
                print(f"YOLO model not found at: {model_path}")
        except Exception as e:
            print(f"Failed to load YOLO model: {e}")

        # Load Scroll Icon Template
        self.scroll_template = None
        try:
            template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'templates', 'scroll_icon.png'))
            if os.path.exists(template_path):
                self.scroll_template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                print(f"Scroll template loaded from: {template_path}")
            else:
                print(f"Scroll template not found at: {template_path}")
        except Exception as e:
            print(f"Failed to load scroll template: {e}")

        # Load Scroll Icon Position
        self.scroll_pos = None
        try:
            pos_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'templates', 'scroll_icon_pos.json'))
            if os.path.exists(pos_path):
                import json
                with open(pos_path, 'r') as f:
                    self.scroll_pos = json.load(f)
                print(f"Scroll position loaded: {self.scroll_pos}")
        except Exception as e:
            print(f"Failed to load scroll position: {e}")

    def run(self):
        self.status_changed.emit("Worker started")
        
        # Initialize DXCam
        # target_monitor=0 is usually the primary monitor. 
        # If the game is on another monitor, this might need adjustment.
        try:
            self.camera = dxcam.create(output_color="BGR")
        except Exception as e:
            print(f"DXCam init error: {e}")
            self.status_changed.emit(f"DXCam Error: {e}")
            return

        print("DXCam initialized. Waiting for game window...")

        while not self.should_stop:
            if self.paused:
                time.sleep(0.1)
                continue

            frame_start = time.time()

            # 1. Get Game Window Location
            rect = game_context.get_window_rect()
            if not rect:
                # Window not found yet
                time.sleep(0.5)
                # print("Waiting for game window...")
                continue
            
            win_left, win_top, win_right, win_bottom = rect

            # 1.5 Dynamic ROI Detection
            now = time.time()
            if self.model and (self.detected_roi is None or now - self.last_roi_update_time > self.ROI_UPDATE_INTERVAL):
                try:
                    # Capture full game window to find the ROI
                    full_region = (win_left, win_top, win_right, win_bottom)
                    full_frame = self.camera.grab(region=full_region)
                    
                    if full_frame is not None:
                        # Run inference
                        results = self.model(full_frame, verbose=False)
                        
                        if results and len(results) > 0:
                            boxes = results[0].boxes
                            if boxes and len(boxes) > 0:
                                # Pick the box with highest confidence
                                best_box = max(boxes, key=lambda x: x.conf[0])
                                x1, y1, x2, y2 = best_box.xyxy[0].cpu().numpy()
                                
                                self.detected_roi = {
                                    "left": int(x1),
                                    "top": int(y1),
                                    "width": int(x2 - x1),
                                    "height": int(y2 - y1)
                                }
                                self.last_roi_update_time = now
                                # print(f"ROI updated: {self.detected_roi}")
                except Exception as e:
                    print(f"ROI detection error: {e}")
            
            # Use detected ROI if available, else fallback
            current_roi = self.detected_roi if self.detected_roi else RELATIVE_ROI

            # Calculate absolute capture region based on current_roi
            abs_left = win_left + current_roi["left"]
            abs_top = win_top + current_roi["top"]
            abs_right = abs_left + current_roi["width"]
            abs_bottom = abs_top + current_roi["height"]

            region = (abs_left, abs_top, abs_right, abs_bottom)

            # 2. Capture with DXCam
            try:
                frame = self.camera.grab(region=region)
            except Exception as e:
                print(f"DXCam grab error: {e}")
                time.sleep(0.1)
                continue
            
            if frame is None:
                # No new frame or error
                time.sleep(0.01)
                continue

            # frame is already BGR because we set output_color="BGR"
            
            # 3. Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 4. Optional scaling
            if SCALE_FACTOR != 1.0:
                width = int(gray.shape[1] * SCALE_FACTOR)
                height = int(gray.shape[0] * SCALE_FACTOR)
                gray = cv2.resize(gray, (width, height), interpolation=cv2.INTER_LINEAR)

            # 5. Preprocessing
            if ENABLE_CLAHE:
                processed = self.clahe.apply(gray)
            else:
                processed = cv2.adaptiveThreshold(
                    gray, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    11, 2
                )

            # 6. Trigger OCR asynchronously
            now = time.time()
            if now - self.last_ocr_time >= OCR_INTERVAL:
                threading.Thread(
                    target=self._run_ocr,
                    args=(processed.copy(), now),
                    daemon=True
                ).start()
                self.last_ocr_time = now
            
            # 6.5 State Machine Logic
            if self.latest_ocr_result and self.map_priority:
                
                # --- STATE: SCANNING ---
                if self.state == "SCANNING":
                    # Clean up old checked maps
                    now = time.time()
                    expired = [k for k, v in self.checked_maps.items() if now - v > self.CHECK_COOLDOWN]
                    for k in expired:
                        del self.checked_maps[k]

                    found_target = False
                    found_priority_index = None
                    
                    # Iterate through priority list in order
                    for idx, priority_map in enumerate(self.map_priority):
                        # Skip if recently checked
                        if priority_map in self.checked_maps:
                            continue

                        for box, text, conf in self.latest_ocr_result:
                            ratio = Levenshtein.ratio(text.lower(), priority_map.lower())
                            
                            if ratio > 0.6:
                                # Improved version/number matching
                                import re
                                text_nums = re.findall(r'\d+', text)
                                map_nums = re.findall(r'\d+', priority_map)
                                
                                if map_nums:
                                    if not text_nums: continue
                                    if text_nums[-1] != map_nums[-1]: continue
                                
                                # Found a valid match
                                if found_priority_index is None or idx < found_priority_index:
                                    found_priority_index = idx
                                    found_target = True
                                    self.last_target_found_time = time.time()
                                    print(f"Target map '{priority_map}' found at priority {idx} (matched OCR: '{text}')")
                                    
                                    if self.click_enabled:
                                        try:
                                            # Click logic
                                            center_x = int(np.mean([p[0] for p in box]))
                                            center_y = int(np.mean([p[1] for p in box]))
                                            
                                            if SCALE_FACTOR != 1.0:
                                                center_x = int(center_x / SCALE_FACTOR)
                                                center_y = int(center_y / SCALE_FACTOR)
                                                
                                            click_x = region[0] + center_x
                                            click_y = region[1] + center_y
                                            
                                            print(f"Clicking on map '{priority_map}' at ({click_x}, {click_y})")
                                            pyautogui.moveTo(click_x, click_y)
                                            pyautogui.click()
                                            
                                            # Update state
                                            self.checked_maps[priority_map] = now
                                            self.current_map_name = priority_map
                                            self.state = "WAITING_FOR_BOSS_LIST"
                                            self.state_timer = now
                                        except Exception as e:
                                            print(f"Click error: {e}")
                                break
                        
                        if found_target:
                            break
                    
                    # Scroll logic (only if we didn't find a target to click)
                    if not found_target and (now - self.last_target_found_time > 2.0) and self.scroll_template is not None:
                        try:
                            search_img = frame
                            res = cv2.matchTemplate(search_img, self.scroll_template, cv2.TM_CCOEFF_NORMED)
                            threshold = 0.7
                            locations = np.where(res >= threshold)
                            
                            if len(locations[0]) > 0:
                                matches = list(zip(*locations[::-1]))
                                if matches:
                                    leftmost_match = min(matches, key=lambda loc: loc[0])
                                    max_loc = leftmost_match
                                    
                                    local_x = max_loc[0] + self.scroll_template.shape[1] // 2
                                    local_y = max_loc[1] + self.scroll_template.shape[0] // 2
                                    icon_x = region[0] + local_x
                                    icon_y = region[1] + local_y
                                    
                                    if now - self.last_scroll_time > 1.0:
                                        if self.scroll_count >= 8:
                                            self.scroll_direction *= -1
                                            self.scroll_count = 0
                                            print(f"Reversing scroll direction")
                                        
                                        scroll_distance = 35 * self.scroll_direction
                                        print(f"Scrolling... ({scroll_distance})")
                                        pyautogui.moveTo(icon_x, icon_y)
                                        pyautogui.dragRel(0, scroll_distance, duration=0.5, button='left')
                                        self.last_scroll_time = now
                                        self.last_scroll_finish_time = time.time()
                                        self.latest_ocr_result = None
                                        self.scroll_count += 1
                        except Exception as e:
                            print(f"Scroll logic error: {e}")

                # --- STATE: WAITING_FOR_BOSS_LIST ---
                elif self.state == "WAITING_FOR_BOSS_LIST":
                    if time.time() - self.state_timer > 0.5: # Wait 500ms
                        self.state = "CHECKING_BOSSES"
                        self.state_timer = time.time()
                        print(f"State -> CHECKING_BOSSES")

                # --- STATE: CHECKING_BOSSES ---
                elif self.state == "CHECKING_BOSSES":
                    # Ensure we have fresh OCR results
                    if self.last_ocr_time > self.state_timer:
                        found_boss = False
                        for box, text, conf in self.latest_ocr_result:
                            # Check for "Dostępny"
                            if "stępn" in text.lower() or Levenshtein.ratio(text.lower(), "dostępny") > 0.7:
                                try:
                                    # Calculate click position (Right edge + 20px)
                                    # box is [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                                    xs = [p[0] for p in box]
                                    ys = [p[1] for p in box]
                                    
                                    min_x, max_x = min(xs), max(xs)
                                    min_y, max_y = min(ys), max(ys)
                                    
                                    center_y = int(np.mean(ys))
                                    
                                    # Target: 20px to the right of the text
                                    target_x = int(max_x + 20)
                                    target_y = center_y
                                    
                                    if SCALE_FACTOR != 1.0:
                                        target_x = int(target_x / SCALE_FACTOR)
                                        target_y = int(target_y / SCALE_FACTOR)
                                        
                                    click_x = region[0] + target_x
                                    click_y = region[1] + target_y
                                    
                                    print(f"Found 'Dostępny' boss, clicking Teleport at ({click_x}, {click_y})")
                                    pyautogui.moveTo(click_x, click_y)
                                    pyautogui.click()
                                    
                                    found_boss = True
                                    
                                    # Lock onto this boss
                                    self.state = "MONITORING_BOSS"
                                    self.locked_boss_roi = {
                                        "min_x": min_x, "max_x": max_x,
                                        "min_y": min_y, "max_y": max_y,
                                        "text": text
                                    }
                                    self.boss_status_change_counter = 0
                                    self.state_timer = time.time()
                                    print(f"Locked onto boss. Monitoring for status change...")
                                except Exception as e:
                                    print(f"Click boss error: {e}")
                                break
                        
                        if not found_boss:
                            # Timeout - No more bosses found
                            if time.time() - self.state_timer > 2.0:
                                print(f"No available bosses found on {self.current_map_name} (Channel {self.current_channel})")
                                
                                # Check if we have more channels to check for this map
                                if self.current_channel < self.num_channels:
                                    self.state = "CHANGING_CHANNEL"
                                    self.current_channel += 1
                                    self.state_timer = time.time()
                                else:
                                    # All channels checked for this map, move to next map
                                    print(f"Finished checking all channels for {self.current_map_name}. Returning to Map Scan.")
                                    self.current_channel = 1 # Reset for next map
                                    self.state = "SCANNING"

                # --- STATE: MONITORING_BOSS ---
                elif self.state == "MONITORING_BOSS":
                    # Check if the locked boss status has changed
                    if self.latest_ocr_result:
                        # Look for "Dostępny" in the locked ROI
                        is_still_available = False
                        
                        # Define a tolerance for position shifts (e.g. 10px)
                        TOLERANCE = 10
                        
                        for box, text, conf in self.latest_ocr_result:
                            # Check if this text block overlaps with our locked ROI
                            xs = [p[0] for p in box]
                            ys = [p[1] for p in box]
                            curr_min_y, curr_max_y = min(ys), max(ys)
                            
                            # Check vertical overlap
                            if (curr_min_y < self.locked_boss_roi["max_y"] + TOLERANCE and 
                                curr_max_y > self.locked_boss_roi["min_y"] - TOLERANCE):
                                
                                # Check if text is "Dostępny"
                                if "stępn" in text.lower() or Levenshtein.ratio(text.lower(), "dostępny") > 0.7:
                                    is_still_available = True
                                    break
                        
                        if not is_still_available:
                            self.boss_status_change_counter += 1
                            # print(f"Boss status might have changed... ({self.boss_status_change_counter}/5)")
                        else:
                            self.boss_status_change_counter = 0 # Reset if we see it again
                            
                        # If status changed consistently for ~1.5 seconds (approx 5 frames at 0.35s interval)
                        if self.boss_status_change_counter >= 5:
                            print("Boss status changed (confirmed). Switching to next boss.")
                            self.state = "CHECKING_BOSSES"
                            self.state_timer = time.time()
                            self.boss_status_change_counter = 0

                # --- STATE: CHANGING_CHANNEL ---
                elif self.state == "CHANGING_CHANNEL":
                    # Wait a bit before typing
                    if time.time() - self.state_timer > 1.0:
                        print(f"Switching to Channel {self.current_channel}...")
                        try:
                            pyautogui.press('enter')
                            time.sleep(0.1)
                            pyautogui.write(f'/ch {self.current_channel}')
                            time.sleep(0.1)
                            pyautogui.press('enter')
                            
                            # Wait for channel switch (e.g. 3 seconds)
                            # In a real scenario, we might want to detect a loading screen or similar
                            # For now, fixed delay
                            time.sleep(3.0)
                            
                            # After switch, go back to checking bosses on this map
                            self.state = "WAITING_FOR_BOSS_LIST" # Wait for list to refresh
                            self.state_timer = time.time()
                            print(f"Channel switched. Waiting for boss list...")
                            
                        except Exception as e:
                            print(f"Channel switch error: {e}")
                            self.state = "SCANNING" # Abort to safe state

            # 7. Display preview
            display_frame = frame.copy()
            
            # FPS counter
            frame_fps = int(1.0 / max(0.00001, (time.time() - frame_start)))
            cv2.putText(display_frame, f"Preview: {frame_fps} FPS", 
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # OCR metrics
            cv2.putText(display_frame, 
                        f"OCR: {self.last_ocr_fps:.1f} FPS ({self.last_ocr_ms:.0f}ms)",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # Draw OCR results
            with self.ocr_lock:
                if self.latest_ocr_result:
                    for box, text, conf in self.latest_ocr_result:
                        if SCALE_FACTOR != 1.0:
                            box = [[int(x / SCALE_FACTOR), int(y / SCALE_FACTOR)] 
                                   for x, y in box]
                        
                        pts = np.array(box, dtype=np.int32)
                        cv2.polylines(display_frame, [pts], True, (0, 255, 0), 2)
                        
                        cv2.putText(display_frame, f"{text} ({float(conf):.2f})",
                                    (pts[0][0], max(10, pts[0][1] - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            cv2.imshow("OCR Live Preview (DXCam)", display_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.status_changed.emit("Worker stopped")
        if self.camera:
            del self.camera 
        cv2.destroyAllWindows()

    def _run_ocr(self, img, timestamp):
        ocr_start = time.time()
        try:
            result, _ = self.ocr(img)
        except Exception as e:
            print(f"OCR error: {e}")
            return

        elapsed = time.time() - ocr_start
        ocr_fps = 1.0 / max(0.00001, elapsed)
        ocr_ms = elapsed * 1000.0

        if result:
            # print(f"\n=== OCR Results ({ocr_fps:.2f} FPS, {ocr_ms:.0f}ms) ===")
            for box, text, conf in result:
                # print(f"  [{int(box[0][0])},{int(box[0][1])}] \"{text}\" (conf: {float(conf):.3f})")
                pass
        else:
            # print(f"OCR: No text found ({ocr_fps:.2f} FPS, {ocr_ms:.0f}ms)")
            pass

        self.last_ocr_fps = ocr_fps
        self.last_ocr_ms = ocr_ms

        with self.ocr_lock:
            if timestamp > self.last_scroll_finish_time:
                self.latest_ocr_result = result
            else:
                # print("Discarding stale OCR result from before scroll")
                pass

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
