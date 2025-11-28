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
        self.ocr_backend = config.get("ocr_backend", "CPU")
        self.show_preview = config.get("show_preview", True)
        
        if self.ocr_backend == "GPU (CUDA)":
            print("Initializing OCR with GPU (CUDA)...")
            try:
                self.ocr = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
            except Exception as e:
                print(f"Failed to init GPU (CUDA) OCR: {e}. Falling back to CPU.")
                self.ocr = RapidOCR()
        elif self.ocr_backend == "GPU (DirectML)":
            print("Initializing OCR with GPU (DirectML)...")
            try:
                # DirectML is often enabled via det_use_dml=True in recent versions
                # If not supported by installed version, it might throw or ignore.
                self.ocr = RapidOCR(det_use_dml=True, cls_use_dml=True, rec_use_dml=True)
            except Exception as e:
                print(f"Failed to init GPU (DirectML) OCR: {e}. Falling back to CPU.")
                self.ocr = RapidOCR()
        else:
            print("Initializing OCR with CPU...")
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

        self.pelerynka_key = config.get("pelerynka_key", "F1")
        self.space_held = False

        # DXCam instance
        self.camera = None

        # OCR state
        self.last_ocr_time = 0
        self.latest_ocr_result = None
        self.ocr_lock = threading.Lock()
        
        # Template Cache
        self.dynamic_templates = config.get("initial_templates", {}).copy()
        self.template_lock = threading.Lock()

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
            # Priority 1: Check for external model.pt in current working directory (for patched/frozen apps)
            external_model_path = os.path.join(os.getcwd(), "model.pt")
            
            # Priority 2: Bundled path relative to this file
            bundled_model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'weights', 'model.pt'))
            
            if os.path.exists(external_model_path):
                self.model = YOLO(external_model_path)
                print(f"YOLO model loaded from EXTERNAL path: {external_model_path}")
            elif os.path.exists(bundled_model_path):
                self.model = YOLO(bundled_model_path)
                print(f"YOLO model loaded from BUNDLED path: {bundled_model_path}")
            else:
                print(f"YOLO model not found. Checked:\n - {external_model_path}\n - {bundled_model_path}")
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
            self.camera.start(target_fps=60, video_mode=True) # Start in video mode for better performance
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
                # In video mode, get_latest_frame is non-blocking and instant
                frame = self.camera.get_latest_frame()
                if frame is not None:
                    # DXCam returns full screen in video mode, need to crop
                    # But wait, create(region=...) is not supported in video mode for some versions?
                    # Let's assume we get full frame and crop manually
                    pass
            except Exception as e:
                print(f"DXCam grab error: {e}")
                time.sleep(0.1)
                continue
            
            if frame is None:
                # No new frame
                time.sleep(0.005) # Very short sleep
                continue
                
            # Crop to region manually since video mode captures full monitor
            # region = (abs_left, abs_top, abs_right, abs_bottom)
            # frame shape is (H, W, C)
            try:
                # Ensure coordinates are within bounds
                h, w = frame.shape[:2]
                r_left = max(0, region[0] - win_left) # DXCam captures relative to monitor? 
                # Actually DXCam captures monitor. win_left is relative to monitor.
                # So region[0] is absolute monitor x.
                
                # Wait, if we use video_mode=True, we get the full monitor frame.
                # We need to crop it using the calculated region.
                frame = frame[region[1]:region[3], region[0]:region[2]]
            except Exception as e:
                # print(f"Crop error: {e}")
                pass

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
            # OPTIMIZATION: Only run OCR if we are missing templates for selected maps or "Dostępny"
            now = time.time()
            
            # Determine required templates
            required_templates = set()
            for m in self.map_priority:
                required_templates.add(f"map:{m}")
            required_templates.add("status:dostepny")
            
            with self.template_lock:
                cached_keys = set(self.dynamic_templates.keys())
                
            missing_templates = required_templates - cached_keys
            ocr_needed = len(missing_templates) > 0
            
            # --- OCR WATCHDOG / FALLBACKS ---
            # Ensure we don't stay blind if templates fail or environment changes
            
            # 1. SCANNING: If we haven't found a target map in > 3.0s, force OCR
            if not ocr_needed and self.state == "SCANNING":
                if (now - self.last_target_found_time > 3.0):
                    ocr_needed = True
            
            # 2. CHECKING_BOSSES: If we are looking for bosses but haven't found one via template,
            # force OCR before we timeout (timeout is usually ~2.0s).
            if not ocr_needed and self.state == "CHECKING_BOSSES":
                # If we have been checking for > 1.0s and haven't locked a boss yet, try OCR
                if (now - self.state_timer > 1.0):
                    ocr_needed = True

            if ocr_needed and (now - self.last_ocr_time >= OCR_INTERVAL):
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

                        # --- FAST PATH: Template Matching ---
                        # Check if we have a cached template for this map
                        template_key = f"map:{priority_map}"
                        rect, conf = self._find_with_template(processed, template_key, threshold=0.85)
                        
                        if rect:
                            x, y, w, h = rect
                            # Calculate click position
                            center_x = x + w // 2
                            center_y = y + h // 2
                            
                            if SCALE_FACTOR != 1.0:
                                center_x = int(center_x / SCALE_FACTOR)
                                center_y = int(center_y / SCALE_FACTOR)
                                
                            click_x = region[0] + center_x
                            click_y = region[1] + center_y
                            
                            print(f"Target map '{priority_map}' found via TEMPLATE (conf: {conf:.2f})")
                            
                            if self.click_enabled:
                                try:
                                    print(f"Clicking on map '{priority_map}' at ({click_x}, {click_y})")
                                    pyautogui.moveTo(click_x, click_y)
                                    time.sleep(np.random.uniform(0.02, 0.03))
                                    pyautogui.click()
                                    
                                    self.checked_maps[priority_map] = now
                                    self.current_map_name = priority_map
                                    self.state = "WAITING_FOR_BOSS_LIST"
                                    self.state_timer = now
                                    found_target = True
                                    self.last_target_found_time = time.time()
                                except Exception as e:
                                    print(f"Click error: {e}")
                            break

                        # --- SLOW PATH: OCR ---
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
                                    
                                    # --- CACHE UPDATE ---
                                    # Extract and save template
                                    try:
                                        # box is [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                                        xs = [p[0] for p in box]
                                        ys = [p[1] for p in box]
                                        min_x, max_x = int(min(xs)), int(max(xs))
                                        min_y, max_y = int(min(ys)), int(max(ys))
                                        
                                        # Add some padding
                                        pad = 2
                                        min_x = max(0, min_x - pad)
                                        min_y = max(0, min_y - pad)
                                        max_x = min(processed.shape[1], max_x + pad)
                                        max_y = min(processed.shape[0], max_y + pad)
                                        
                                        template_img = processed[min_y:max_y, min_x:max_x].copy()
                                        with self.template_lock:
                                            self.dynamic_templates[template_key] = template_img
                                        # print(f"Cached template for {priority_map}")
                                    except Exception as e:
                                        print(f"Failed to cache template: {e}")
                                    
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
                                            time.sleep(np.random.uniform(0.02, 0.03))
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
                                    
                                    # Check if scrollbar is at the bottom or top of the ROI
                                    # region is (abs_left, abs_top, abs_right, abs_bottom)
                                    # local_y is relative to region top
                                    roi_height = region[3] - region[1]
                                    
                                    is_at_bottom = local_y > (roi_height * 0.9)
                                    is_at_top = local_y < (roi_height * 0.1)
                                    
                                    if is_at_bottom and self.scroll_direction == 1:
                                        print("Scrollbar at bottom, reversing to UP.")
                                        self.scroll_direction = -1
                                        self.scroll_count = 0
                                    elif is_at_top and self.scroll_direction == -1:
                                        print("Scrollbar at top, reversing to DOWN.")
                                        self.scroll_direction = 1
                                        self.scroll_count = 0
                                    
                                    elif now - self.last_scroll_time > 1.0:
                                        # Remove the arbitrary 8-scroll reversal if we rely on visual detection
                                        # But keep a failsafe if needed, or just rely on boundaries.
                                        # For now, let's trust the visual boundaries more.
                                        
                                        scroll_distance = 35 * self.scroll_direction
                                        
                                        # Double check boundaries before scrolling
                                        if is_at_bottom and scroll_distance > 0:
                                            self.scroll_direction = -1
                                            scroll_distance = -35
                                            print("Boundary check: Bottom reached, forcing UP.")
                                        elif is_at_top and scroll_distance < 0:
                                            self.scroll_direction = 1
                                            scroll_distance = 35
                                            print("Boundary check: Top reached, forcing DOWN.")
                                        
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
                    
                    # --- FAST PATH: Template Matching for "Dostępny" ---
                    template_key = "status:dostepny"
                    rect, conf = self._find_with_template(processed, template_key, threshold=0.80)
                    
                    if rect:
                        x, y, w, h = rect
                        # Calculate click position (Right edge + 20px)
                        target_x = int(x + w + 20)
                        target_y = int(y + h // 2)
                        
                        if SCALE_FACTOR != 1.0:
                            target_x = int(target_x / SCALE_FACTOR)
                            target_y = int(target_y / SCALE_FACTOR)
                            
                        click_x = region[0] + target_x
                        click_y = region[1] + target_y
                        
                        print(f"Found 'Dostępny' boss via TEMPLATE (conf: {conf:.2f}), clicking Teleport at ({click_x}, {click_y})")
                        try:
                            pyautogui.moveTo(click_x, click_y)
                            pyautogui.click()
                            
                            # Lock onto this boss
                            self.state = "MONITORING_BOSS"
                            self.locked_boss_roi = {
                                "min_x": x, "max_x": x + w,
                                "min_y": y, "max_y": y + h,
                                "text": "Dostępny"
                            }
                            self.boss_status_change_counter = 0
                            self.state_timer = time.time()
                            print(f"Locked onto boss. Monitoring for status change...")
                        except Exception as e:
                            print(f"Click boss error: {e}")
                    
                    # --- SLOW PATH: OCR ---
                    # Ensure we have fresh OCR results
                    elif self.last_ocr_time > self.state_timer:
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
                                    
                                    # --- CACHE UPDATE ---
                                    try:
                                        pad = 2
                                        t_min_x = max(0, int(min_x) - pad)
                                        t_min_y = max(0, int(min_y) - pad)
                                        t_max_x = min(processed.shape[1], int(max_x) + pad)
                                        t_max_y = min(processed.shape[0], int(max_y) + pad)
                                        
                                        template_img = processed[t_min_y:t_max_y, t_min_x:t_max_x].copy()
                                        with self.template_lock:
                                            self.dynamic_templates[template_key] = template_img
                                        # print("Cached template for 'Dostępny'")
                                    except Exception as e:
                                        print(f"Failed to cache 'Dostępny' template: {e}")

                                    # Target: 20px to the right of the text
                                    target_x = int(max_x + 20)
                                    target_y = center_y
                                    
                                    if SCALE_FACTOR != 1.0:
                                        target_x = int(target_x / SCALE_FACTOR)
                                        target_y = int(target_y / SCALE_FACTOR)
                                        
                                    click_x = region[0] + target_x
                                    click_y = region[1] + target_y
                                    
                                    self.state_timer = time.time()
                                else:
                                    # All channels checked for this map, move to next map
                                    print(f"Finished checking all channels for {self.current_map_name}. Returning to Map Scan.")
                                    self.current_channel = 1 # Reset for next map
                                    self.state = "SCANNING"

                # --- STATE: MONITORING_BOSS ---
                elif self.state == "MONITORING_BOSS":
                    # --- PELERYNKA & SPACEBAR LOGIC ---
                    if not self.space_held:
                        print(f"Boss locked. Pressing {self.pelerynka_key} and holding Space.")
                        try:
                            # Press Pelerynka key once
                            pyautogui.press(self.pelerynka_key.lower())
                            time.sleep(0.05)
                            
                            # Hold Spacebar
                            pyautogui.keyDown('space')
                            self.space_held = True
                        except Exception as e:
                            print(f"Input error: {e}")

                    # Check if the locked boss status has changed
                    # FAST PATH: Template Matching
                    template_key = "status:dostepny"
                    is_still_available = False
                    
                    # 1. Try template matching first if available
                    with self.template_lock:
                        has_template = template_key in self.dynamic_templates
                        
                    if has_template:
                        # Crop the locked ROI from the current frame to search within
                        try:
                            l_min_x = int(max(0, self.locked_boss_roi["min_x"] - 10))
                            l_min_y = int(max(0, self.locked_boss_roi["min_y"] - 10))
                            l_max_x = int(min(processed.shape[1], self.locked_boss_roi["max_x"] + 10))
                            l_max_y = int(min(processed.shape[0], self.locked_boss_roi["max_y"] + 10))
                            
                            roi_img = processed[l_min_y:l_max_y, l_min_x:l_max_x]
                            
                            # Search for template within this small ROI
                            # If we don't find it, it means the "Dostępny" text is gone (boss taken/despawned)
                            # Increased threshold to 0.90 to strictly match "Dostępny" and reject timers
                            rect, conf = self._find_with_template(roi_img, template_key, threshold=0.90)
                            if rect:
                                is_still_available = True
                                # print(f"Boss status confirmed via TEMPLATE (conf: {conf:.2f})")
                            else:
                                # Template not found in the expected spot -> Boss likely gone
                                is_still_available = False
                                # print(f"Boss status template mismatch (conf: {conf:.2f} < 0.90)")
                                
                        except Exception as e:
                            print(f"Monitoring template error: {e}")
                            # Fallback to OCR if template logic crashes
                            is_still_available = False 
                    
                    # 2. Fallback to OCR ONLY if we don't have a template yet
                    elif not has_template and self.latest_ocr_result:
                        # ... (OCR fallback logic) ...
                        pass # (kept as is)

                    # ... (rest of logic) ...

            # 7. Display preview
            if self.show_preview:
                display_frame = frame.copy()
                
                # FPS counter
                frame_fps = int(1.0 / max(0.00001, (time.time() - frame_start)))
                cv2.putText(display_frame, f"Preview: {frame_fps} FPS", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                # OCR metrics
                is_stale = (time.time() - self.last_ocr_time) > 1.0
                status_color = (0, 255, 0) if not ocr_needed else (0, 255, 255)
                
                if not ocr_needed:
                    status_text = "OCR: Idle (All Cached)"
                    if is_stale:
                        status_text += " [Results Stale]"
                else:
                    status_text = f"OCR: Active ({self.last_ocr_fps:.1f} FPS)"
                
                cv2.putText(display_frame, status_text,
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

                # Draw OCR results
                with self.ocr_lock:
                    if self.latest_ocr_result:
                        # Fade out stale results visually
                        color = (0, 255, 0) if not is_stale else (0, 100, 0)
                        
                        for box, text, conf in self.latest_ocr_result:
                            if SCALE_FACTOR != 1.0:
                                box = [[int(x / SCALE_FACTOR), int(y / SCALE_FACTOR)] 
                                       for x, y in box]
                            
                            pts = np.array(box, dtype=np.int32)
                            cv2.polylines(display_frame, [pts], True, color, 2)
                            
                            cv2.putText(display_frame, f"{text} ({float(conf):.2f})",
                                        (pts[0][0], max(10, pts[0][1] - 5)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                # Visualize Cached Templates (Bottom of screen)
                with self.template_lock:
                    y_offset = display_frame.shape[0] - 60
                    x_offset = 10
                    for key, tmpl in self.dynamic_templates.items():
                        try:
                            # Resize for thumbnail
                            h, w = tmpl.shape[:2]
                            scale = 40 / h
                            thumb = cv2.resize(tmpl, (int(w * scale), 40))
                            
                            # Convert to BGR if grayscale
                            if len(thumb.shape) == 2:
                                thumb = cv2.cvtColor(thumb, cv2.COLOR_GRAY2BGR)
                                
                            # Draw thumbnail
                            h_t, w_t = thumb.shape[:2]
                            if y_offset + h_t < display_frame.shape[0] and x_offset + w_t < display_frame.shape[1]:
                                display_frame[y_offset:y_offset+h_t, x_offset:x_offset+w_t] = thumb
                                cv2.rectangle(display_frame, (x_offset, y_offset), (x_offset+w_t, y_offset+h_t), (255, 0, 0), 1)
                                cv2.putText(display_frame, key.split(':')[-1], (x_offset, y_offset-5), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 200, 0), 1)
                                x_offset += w_t + 10
                        except:
                            pass

                cv2.imshow("OCR Live Preview (DXCam)", display_frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                # If preview disabled, sleep briefly to prevent CPU starvation
                # This allows the OCR thread and DXCam background thread to run smoothly
                time.sleep(0.01)

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
        if self.camera:
            self.camera.stop()
        
        # Release spacebar if held
        if self.space_held:
            print("Stopping worker: Releasing Spacebar.")
            try:
                pyautogui.keyUp('space')
                self.space_held = False
            except:
                pass
                
        self.wait()

    def pause(self):
        self.paused = True
        self.status_changed.emit("Paused")

    def resume(self):
        self.paused = False
        self.status_changed.emit("Resumed")

    def reset(self):
        self.status_changed.emit("Reset")

    def _find_with_template(self, image, template_key, threshold=0.8):
        """
        Attempts to find a cached template in the given image.
        Returns ((x, y, w, h), confidence) or (None, 0.0)
        """
        with self.template_lock:
            if template_key not in self.dynamic_templates:
                return None, 0.0
            template = self.dynamic_templates[template_key]

        try:
            # Ensure image is grayscale if template is grayscale
            if len(template.shape) == 2 and len(image.shape) == 3:
                search_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                search_img = image

            # Template matching - SQDIFF_NORMED is often faster and robust
            res = cv2.matchTemplate(search_img, template, cv2.TM_SQDIFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            # For SQDIFF, smaller value means better match (0.0 is perfect)
            # Threshold needs to be inverted: 0.8 confidence -> 0.2 diff
            match_quality = 1.0 - min_val
            
            if match_quality >= threshold:
                h, w = template.shape[:2]
                return (min_loc[0], min_loc[1], w, h), match_quality
            
            return None, match_quality
        except Exception as e:
            # print(f"Template match error for {template_key}: {e}")
            return None, 0.0
