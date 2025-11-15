"""
Boss detection worker using QThread for non-blocking image recognition and automation.
Refactored from standalone boss farming script into modular QThread-based worker.
"""

import pyautogui
import cv2
import numpy as np
import time
from datetime import datetime
from PySide6.QtCore import QThread, Signal
import os
import sys
from pynput.keyboard import Controller, Key


class BossDetectionWorker(QThread):
    """
    Worker thread for boss detection and farming automation.
    
    Signals:
    - frame_captured: emitted with processed frame (np.ndarray) for UI preview
    - status_changed: emitted with status message (str)
    - target_found: emitted when target is locked
    - target_lost: emitted when target is lost
    - detection_triggered: emitted when a click action is performed
    - stats_updated: emitted with current stats (targets_found, channels_cycled, swaps_performed)
    """

    frame_captured = Signal(np.ndarray)
    status_changed = Signal(str)
    target_found = Signal()
    target_lost = Signal()
    detection_triggered = Signal(dict)  # {timestamp, click_x, click_y, confidence}
    stats_updated = Signal(dict)  # {targets_found, channels_cycled, swaps_performed}
    channel_switched = Signal(int)  # emitted with channel index when switched

    def __init__(self, config: dict):
        """
        Initialize the boss detection worker.
        
        Args:
            config (dict): Configuration containing:
                - region: (left, top, width, height)
                - template_path: path to template image
                - match_threshold: float between 0 and 1
                - click_offset_x: int pixel offset for click
                - num_channels: int number of channels to cycle
                - channel_switch_interval: float seconds between switches
                - lock_timeout: float seconds before unlocking
                - swap_interval: float seconds between periodic swaps
                - swap_x_offset: int x offset for swaps
                - swap_y_offsets: list of y offsets for swaps
        """
        super().__init__()
        self.config = config
        self.running = False
        self.paused = False
        self.should_stop = False

        # State variables
        self.locked = False
        self.locked_top_left = None
        self.locked_bottom_right = None
        self.lock_start_time = 0.0
        self.current_channel = 0
        self.last_switch_time = 0.0
        self.last_swap_time = time.time()

        # Track last clicked target center and unavailable centers
        self.last_clicked_center = None          # (x, y) of last click attempted
        self.last_click_time = 0.0
        # list of tuples (x, y, marked_time)
        self.unavailable_centers = []

        # Stats counters
        self.targets_found = 0
        self.channels_cycled = 0
        self.swaps_performed = 0

        # Load template
        template_path = config.get("template_path", "assets/templates/dostepny_template.png")

        # If running as a frozen EXE, PyInstaller extracts datas to sys._MEIPASS.
        # Try to resolve the template from the bundle if the configured path is not found.
        if not os.path.exists(template_path) and getattr(sys, "frozen", False):
            bundled_path = os.path.join(sys._MEIPASS, *template_path.split("/"))
            if os.path.exists(bundled_path):
                template_path = bundled_path

        if not os.path.exists(template_path):
            self.status_changed.emit(f"ERROR: Template not found at {template_path}")
            raise FileNotFoundError(f"Template not found: {template_path}")

        self.template_gray = cv2.imread(template_path, 0)
        if self.template_gray is None:
            self.status_changed.emit(f"ERROR: Could not load template from {template_path}")
            raise ValueError(f"Could not load template: {template_path}")

        self.template_height, self.template_width = self.template_gray.shape
        self.status_changed.emit(f"Template loaded: {template_path}")

        # Keyboard controller for pynput
        self.keyboard = Controller()

        # Default preview frame
        self.last_frame = np.zeros((200, 200, 3), dtype=np.uint8)

    def run(self):
        """Main loop for detection and automation."""
        self.running = True
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.status_changed.emit(f"[{timestamp}] Detection worker started")

        try:
            while not self.should_stop:
                # Handle periodic swaps
                if time.time() - self.last_swap_time >= self.config.get("swap_interval", 300):
                    self._perform_swaps()

                # Skip if paused
                if self.paused:
                    time.sleep(0.1)
                    continue

                # Main detection loop
                triggered = self._process_frame()

                # If we recently clicked a target and it persists beyond unavailable_timeout,
                # mark that specific center as unavailable and switch channel.
                unavailable_timeout = self.config.get("unavailable_timeout", 10.0)
                if self.last_clicked_center and (time.time() - self.last_click_time) > unavailable_timeout:
                    try:
                        if self._is_center_present_in_last_frame(self.last_clicked_center):
                            self._mark_unavailable(self.last_clicked_center)
                            # clear last clicked so we don't re-evaluate immediately
                            self.last_clicked_center = None
                            # switch channel because this specific boss appears unkillable
                            self._maybe_switch_channel()
                        else:
                            # target disappeared — normal case; clear marker
                            self.last_clicked_center = None
                    except Exception as e:
                        self.status_changed.emit(f"Unavailable-check error: {e}")

                # Handle lock timeout
                if (
                    self.locked
                    and time.time() - self.lock_start_time
                    > self.config.get("lock_timeout", 10.0)
                ):
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.status_changed.emit(f"[{timestamp}] Lock timeout - switching channel")
                    self._release_space_safely()
                    self._maybe_switch_channel()

                # Switch channel if not locked
                if not triggered and not self.locked:
                    self._maybe_switch_channel()

                time.sleep(self.config.get("loop_delay", 0.1))

        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.status_changed.emit(f"[{timestamp}] ERROR: {str(e)}")

        finally:
            self._release_space_safely()
            self.running = False
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.status_changed.emit(f"[{timestamp}] Detection worker stopped")

    def stop(self):
        """Stop the detection worker."""
        self.should_stop = True
        self.wait()

    def pause(self):
        """Pause detection (keep thread running)."""
        self.paused = True
        self.status_changed.emit("Detection paused")

    def resume(self):
        """Resume detection."""
        self.paused = False
        self.status_changed.emit("Detection resumed")

    def reset(self):
        """Reset all state variables."""
        self.locked = False
        self.locked_top_left = None
        self.locked_bottom_right = None
        self.lock_start_time = 0.0
        self.current_channel = 0
        self.last_switch_time = 0.0
        self._release_space_safely()
        self.status_changed.emit("Detection reset")
        self.target_lost.emit()

    def _process_frame(self) -> bool:
        """
        Capture and process a frame for template matching.
        
        Returns:
            bool: True if a new target was detected and clicked, False otherwise
        """
        try:
            region = self.config.get("region", (250, 120, 260, 215))
            screenshot = pyautogui.screenshot(region=region)
            screenshot = np.array(screenshot)
            screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            gray_screenshot = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)

            # Check locked region first
            if self.locked and self.locked_top_left and self.locked_bottom_right:
                x1, y1 = self.locked_top_left
                x2, y2 = self.locked_bottom_right
                h, w = gray_screenshot.shape

                if x2 <= w and y2 <= h:
                    roi = gray_screenshot[y1:y2, x1:x2]
                    if roi.shape == self.template_gray.shape:
                        result = cv2.matchTemplate(
                            roi, self.template_gray, cv2.TM_CCOEFF_NORMED
                        )
                        _, lock_val, _, _ = cv2.minMaxLoc(result)
                        threshold = self.config.get("match_threshold", 0.8)

                        if lock_val >= threshold:
                            cv2.rectangle(
                                screenshot_bgr,
                                self.locked_top_left,
                                self.locked_bottom_right,
                                (0, 255, 0),
                                2,
                            )
                            self.last_frame = screenshot_bgr
                            self.frame_captured.emit(screenshot_bgr)
                            return False

            # Target lost
            self.status_changed.emit("Locked target lost - unlocking")
            self.locked = False
            self.locked_top_left = self.locked_bottom_right = None
            self.lock_start_time = 0.0
            self._release_space_safely()
            self.target_lost.emit()

            # Search for new target
            result = cv2.matchTemplate(
                gray_screenshot, self.template_gray, cv2.TM_CCOEFF_NORMED
            )
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            threshold = self.config.get("match_threshold", 0.8)

            if max_val >= threshold:
                top_left = max_loc
                bottom_right = (
                    top_left[0] + self.template_width,
                    top_left[1] + self.template_height,
                )
                cv2.rectangle(screenshot_bgr, top_left, bottom_right, (0, 0, 255), 2)

                # Compute center of detected template for per-boss tracking
                center = (top_left[0] + self.template_width // 2, top_left[1] + self.template_height // 2)

                # If this center was previously marked unavailable, skip clicking it
                if self._is_center_unavailable(center):
                    self.status_changed.emit(f"Skipping marked-unavailable boss at {center}")
                    self.last_frame = screenshot_bgr
                    self.frame_captured.emit(screenshot_bgr)
                    return False

                # Calculate click position
                region_left, region_top, _, _ = region
                click_x = region_left + bottom_right[0] + self.config.get("click_offset_x", 20)
                click_y = region_top + top_left[1] + self.template_height // 2

                self.status_changed.emit(
                    f"Found target (confidence: {max_val:.3f}) - clicking"
                )

                # Perform clicks and key presses
                pyautogui.moveTo(click_x, click_y)
                pyautogui.click()

                # record that we clicked this center; if it persists beyond timeout we'll mark unavailable
                self.last_clicked_center = center
                self.last_click_time = time.time()

                try:
                    self._press_key("F4")
                    time.sleep(0.1)
                    self._release_key("F4")
                    self._press_key("SPACEBAR")
                except Exception as e:
                    self.status_changed.emit(f"Key press error: {str(e)}")

                # Lock target
                self.locked = True
                self.locked_top_left = top_left
                self.locked_bottom_right = bottom_right
                self.lock_start_time = time.time()

                self.last_frame = screenshot_bgr
                self.frame_captured.emit(screenshot_bgr)
                self.target_found.emit()
                self.targets_found += 1
                self._emit_stats()
                self.detection_triggered.emit(
                    {
                        "timestamp": time.time(),
                        "click_x": click_x,
                        "click_y": click_y,
                        "confidence": float(max_val),
                    }
                )
                return True
            else:
                self.last_frame = screenshot_bgr
                self.frame_captured.emit(screenshot_bgr)
                return False

        except Exception as e:
            self.status_changed.emit(f"Frame processing error: {str(e)}")
            return False

    def _switch_to_channel(self, channel_index: int, hotkey_config: dict = None):
        """Switch to a specific channel using keyboard shortcuts.
        
        Args:
            channel_index: Channel number (1-12)
            hotkey_config: Dict with 'key' and 'modifier' (e.g., {'key': 'F1', 'modifier': 'shift'})
                          If None, uses default LSHIFT+Fn sequence
        """
        if channel_index < 1 or channel_index > self.config.get("num_channels", 6):
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm
        self.status_changed.emit(f"[{timestamp}] Switching to channel {channel_index}")

        try:
            if hotkey_config:
                # Use configured hotkey
                self._press_hotkey_combo(hotkey_config.get('key'), hotkey_config.get('modifier'))
            else:
                # Default: LSHIFT+F{channel_index}
                key_name = f"F{channel_index}"
                self._press_hotkey_combo(key_name, 'shift')
        except Exception as e:
            self.status_changed.emit(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Channel switch error: {str(e)}")

        self.current_channel = channel_index
        self.last_switch_time = time.time()
        self.channels_cycled += 1
        # Clear unavailable centers when switching channels (bosses may have been killed by others)
        self.unavailable_centers = []
        self.channel_switched.emit(channel_index)
        self._emit_stats()

    def _maybe_switch_channel(self):
        """Switch channel if interval has elapsed."""
        now = time.time()
        interval = self.config.get("channel_switch_interval", 2.0)

        if now - self.last_switch_time < interval:
            return

        if self.current_channel == 0:
            self._switch_to_channel(self.config.get("start_channel", 1))
            return

        next_channel = self.current_channel + 1
        if next_channel > self.config.get("num_channels", 6):
            next_channel = 1
        self._switch_to_channel(next_channel)

    def _perform_swaps(self):
        """Perform periodic swap clicks."""
        region = self.config.get("region", (250, 120, 260, 215))
        region_left, region_top, _, _ = region
        swap_x_offset = self.config.get("swap_x_offset", -100)
        swap_y_offsets = self.config.get("swap_y_offsets", [0, 50, 100])

        x = region_left + swap_x_offset
        y_positions = [region_top + y for y in swap_y_offsets]

        self.status_changed.emit(f"Performing periodic swaps at {len(y_positions)} positions")

        for cy in y_positions:
            pyautogui.moveTo(x, cy)
            pyautogui.click()
            time.sleep(0.1)

        self.last_swap_time = time.time()
        self.swaps_performed += 1
        self._emit_stats()

    def _press_hotkey_combo(self, key_name: str, modifier: str = None):
        """Press a key combination using pynput.
        
        Args:
            key_name: Key name (e.g., 'F1', 'A', 'space')
            modifier: Modifier key ('shift', 'ctrl', 'alt', or None)
        """
        key_map = {
            'F1': Key.f1, 'F2': Key.f2, 'F3': Key.f3, 'F4': Key.f4,
            'F5': Key.f5, 'F6': Key.f6, 'F7': Key.f7, 'F8': Key.f8,
            'F9': Key.f9, 'F10': Key.f10, 'F11': Key.f11, 'F12': Key.f12,
            'space': Key.space,
        }
        
        modifier_map = {
            'shift': Key.shift,
            'ctrl': Key.ctrl,
            'alt': Key.alt,
        }
        
        # Get the key object
        key = key_map.get(key_name, key_name)
        
        # Press modifier if specified
        if modifier and modifier.lower() in modifier_map:
            mod_key = modifier_map[modifier.lower()]
            self.keyboard.press(mod_key)
            time.sleep(0.02)
        
        # Press the key
        self.keyboard.press(key)
        time.sleep(0.02)
        
        # Release the key
        self.keyboard.release(key)
        time.sleep(0.02)
        
        # Release modifier if specified
        if modifier and modifier.lower() in modifier_map:
            mod_key = modifier_map[modifier.lower()]
            self.keyboard.release(mod_key)
            time.sleep(0.02)

    @staticmethod
    def _press_key(key: str):
        """Press a key using pyautogui."""
        # Map common key names to pyautogui format
        key_map = {
            "LSHIFT": "shift",
            "SPACEBAR": "space",
        }
        key = key_map.get(key, key.lower())
        pyautogui.press(key)

    @staticmethod
    def _release_key(key: str):
        """Release a key (pyautogui doesn't have explicit release for press())."""
        pass

    @staticmethod
    def _release_space_safely():
        """Safely release space key."""
        try:
            pyautogui.keyUp("space")
        except Exception:
            pass

    def _emit_stats(self):
        """Emit current stats to UI."""
        stats = {
            "targets_found": self.targets_found,
            "channels_cycled": self.channels_cycled,
            "swaps_performed": self.swaps_performed,
        }
        self.stats_updated.emit(stats)

    # ---------------------------
    # Helper methods for per-boss unavailable logic
    # ---------------------------
    def _center_from_top_left(self, top_left):
        return (top_left[0] + self.template_width // 2, top_left[1] + self.template_height // 2)

    def _is_center_unavailable(self, center, tol=30):
        """Return True if center is within tol px of any marked-unavailable center."""
        for cx, cy, _ in self.unavailable_centers:
            if (center[0] - cx) ** 2 + (center[1] - cy) ** 2 <= tol * tol:
                return True
        return False

    def _mark_unavailable(self, center):
        """Mark a specific center as unavailable (timestamped)."""
        self.unavailable_centers.append((center[0], center[1], time.time()))
        self.status_changed.emit(f"Marked boss at {center} as unavailable (will be skipped)")

    def _is_center_present_in_last_frame(self, center, tol=40):
        """Check whether the same template appears near center in last_frame with sufficient confidence."""
        if not hasattr(self, "last_frame") or self.last_frame is None:
            return False
        try:
            gray = cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray, self.template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            loc_center = (max_loc[0] + self.template_width // 2, max_loc[1] + self.template_height // 2)
            if (loc_center[0] - center[0]) ** 2 + (loc_center[1] - center[1]) ** 2 <= tol * tol:
                return max_val >= self.config.get("match_threshold", 0.8)
            return False
        except Exception as e:
            self.status_changed.emit(f"Presence-check error: {e}")
            return False
