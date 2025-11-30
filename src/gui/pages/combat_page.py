"""
Combat page with properly structured tabs and repaired TeleporterTab (OCR scan fixed).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton, 
    QHBoxLayout, QMessageBox, QInputDialog, QCheckBox, QSpinBox, QComboBox
)
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QImage

from gui.controllers.teleporter_tab_farming import BossFarmingManager
from gui.controllers.teleporter_tab_worker import RELATIVE_ROI
from gui.widgets.draggable_list import DraggableListWidget

import Levenshtein
from rapidocr_onnxruntime import RapidOCR
import cv2
import numpy as np
import dxcam
import os
import json
import mss

from game_context import game_context


##############################################
# MAIN COMBAT PAGE
##############################################

class combat_page(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Combat Farming")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(TeleporterTab(), "Teleporter Farming")
        tabs.addTab(BossFarmingTab(), "Boss Farming")
        tabs.addTab(MetinFarmingTab(), "Metin Farming")
        layout.addWidget(tabs)

        self.setLayout(layout)

    def load_settings(self, data):
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QTabWidget):
                teleporter = widget.widget(0)
                if isinstance(teleporter, TeleporterTab):
                    t_settings = data.get("teleporter", {})
                    # Inject global channel count setting
                    t_settings["num_channels"] = data.get("channel_count", 1)
                    teleporter.load_settings(t_settings)

    def get_settings(self):
        settings = {}
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QTabWidget):
                teleporter = widget.widget(0)
                if isinstance(teleporter, TeleporterTab):
                    settings["teleporter"] = teleporter.get_settings()
        return settings

    def stop_detection(self):
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QTabWidget):
                # Iterate through all tabs
                for tab_index in range(widget.count()):
                    tab = widget.widget(tab_index)
                    if hasattr(tab, "stop_detection"):
                        tab.stop_detection()


##############################################
# TELEPORTER TAB — FIXED
##############################################

class TeleporterTab(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.manager = BossFarmingManager()
        self.ocr = RapidOCR()
        
        # Load YOLO model for ROI detection
        self.yolo_model = None
        try:
            from ultralytics import YOLO
            model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'weights', 'summon_window.pt'))
            if os.path.exists(model_path):
                self.yolo_model = YOLO(model_path)
                print(f"YOLO model loaded for map scanning: {model_path}")
            else:
                print(f"YOLO model not found at: {model_path}")
        except Exception as e:
            print(f"Failed to load YOLO model: {e}")
        
        self.init_ui()

        # Known map list
        self.known_maps = [
            "Dolina Orków", 
            "Góra Sohan", 
            "Pustynia", 
            "Loch Pająków", 
            "Czerwony Las", 
            "Grota Wygnańców V2", 
            "Grota Wygnańców V3", 
            "Grota Wygnańców V4", 
            "Mroczna Krypta V1",
            "Mroczna Krypta V2",
            "Mroczna Krypta V3",
            "Mroczna Krypta V4", 
            "Mroczna Krypta V5"
        ]
        
        self.num_channels = 1

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Label
        lbl = QLabel("Map Priority (Drag to reorder):")
        lbl.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(lbl)
        # Draggable list
        self.map_list = DraggableListWidget()
        self.map_list.setMinimumHeight(200)
        layout.addWidget(self.map_list)

        # Controls Layout
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)

        # Row 1: Actions
        row1 = QHBoxLayout()
        btn_scan = QPushButton("Scan Maps")
        btn_scan.clicked.connect(self.scan_maps)
        row1.addWidget(btn_scan)

        btn_select_icon = QPushButton("Setup Scroll Icon")
        btn_select_icon.clicked.connect(self.setup_scroll_icon)
        row1.addWidget(btn_select_icon)
        controls_layout.addLayout(row1)

        # Row 2: Settings
        row2 = QHBoxLayout()
        
        # Pelerynka
        lbl_cape = QLabel("Cape Key:")
        row2.addWidget(lbl_cape)
        
        self.key_combo = QComboBox()
        self.key_combo.addItems(["F1", "F2", "F3", "F4", "1", "2", "3", "4"])
        self.key_combo.setCurrentText("F1")
        self.key_combo.setStyleSheet("""
            QComboBox {
                background: #2b2b2b;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 4px;
                min-width: 50px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        row2.addWidget(self.key_combo)
        
        row2.addStretch()
        
        self.preview_checkbox = QCheckBox("Preview")
        self.preview_checkbox.setChecked(True)
        row2.addWidget(self.preview_checkbox)
        
        # Stuck Boss Settings
        self.ignore_stuck_checkbox = QCheckBox("Ignore Stuck")
        self.ignore_stuck_checkbox.setChecked(True)
        row2.addWidget(self.ignore_stuck_checkbox)

        self.stuck_timeout_spin = QSpinBox()
        self.stuck_timeout_spin.setRange(5, 300)
        self.stuck_timeout_spin.setValue(30)
        self.stuck_timeout_spin.setSuffix("s")
        self.stuck_timeout_spin.setStyleSheet("""
            QSpinBox {
                background: #2b2b2b;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 4px;
            }
        """)
        row2.addWidget(self.stuck_timeout_spin)
        
        controls_layout.addLayout(row2)

        # Row 3: Start Button
        self.toggle_btn = QPushButton("Start Detection")
        self.toggle_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.toggle_btn.clicked.connect(self.toggle_farming)
        controls_layout.addWidget(self.toggle_btn)

        layout.addLayout(controls_layout)
        layout.addStretch()
        self.setLayout(layout)

    def toggle_farming(self):
        if self.toggle_btn.text() == "Start Detection":
            priority_list = self.map_list.get_checked_items()
            # click_enabled is now always True
            click_enabled = True
            
            # Get num_channels and hotkeys from SettingsPage
            num_channels = 1  # Default
            channel_hotkeys = {}
            if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'settings_page'):
                settings = self.main_window.settings_page.get_settings()
                num_channels = settings.get('channel_count', 1)
                channel_hotkeys = settings.get('channel_hotkeys', {})
            
            pelerynka_key = self.key_combo.currentText()
            show_preview = self.preview_checkbox.isChecked()
            ignore_stuck = self.ignore_stuck_checkbox.isChecked()
            stuck_timeout = self.stuck_timeout_spin.value()
            
            print(f"Starting with priority: {priority_list}, click_enabled: {click_enabled}, channels: {num_channels}, key: {pelerynka_key}, preview: {show_preview}, hotkeys: {channel_hotkeys}, ignore_stuck: {ignore_stuck}, timeout: {stuck_timeout}")
            
            self.manager.start_boss_farming(priority_list, click_enabled=click_enabled, num_channels=num_channels, pelerynka_key=pelerynka_key, show_preview=show_preview, channel_hotkeys=channel_hotkeys, ignore_stuck=ignore_stuck, stuck_timeout=stuck_timeout)
            self.toggle_btn.setText("Stop Detection")
            self.toggle_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
            self.status_label.setText("Status: Running")
        else:
            self.manager.stop_boss_farming()
            self.toggle_btn.setText("Start Detection")
            self.toggle_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
            self.status_label.setText("Status: Stopped")
    
    def stop_detection(self):
        if self.manager:
            self.manager.stop_boss_farming()
            self.manager.stop_boss_farming()
            self.toggle_btn.setText("Start Detection")
            self.toggle_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
            self.status_label.setText("Status: Emergency Stopped")

    ##############################################
    # FIXED OCR SCAN LOGIC
    ##############################################

    def scan_maps(self):
        try:
            win_rect = game_context.get_window_rect()
            if not win_rect:
                QMessageBox.warning(self, "Error", "Game window not found.")
                return

            left, top, right, bottom = win_rect
            win_width = right - left
            win_height = bottom - top

            # Capture full game window
            full_region = {
                "left": left,
                "top": top,
                "width": win_width,
                "height": win_height
            }

            with mss.mss() as sct:
                raw = np.array(sct.grab(full_region))
            full_frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

            # Try YOLO detection first
            roi_frame = None
            
            if self.yolo_model:
                try:
                    # Run YOLO inference
                    results = self.yolo_model(full_frame, verbose=False)
                    
                    # Check if any detections
                    if len(results) > 0 and len(results[0].boxes) > 0:
                        # Get the first detection (highest confidence)
                        box = results[0].boxes[0]
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        # Crop to detected ROI
                        roi_frame = full_frame[y1:y2, x1:x2]
                        print(f"YOLO detected summon window at: ({x1},{y1}) -> ({x2},{y2})")
                    else:
                        print("YOLO: No summon window detected, falling back to RELATIVE_ROI")
                except Exception as e:
                    print(f"YOLO detection error: {e}")
            
            # Fallback to RELATIVE_ROI if YOLO failed or not available
            if roi_frame is None:
                roi_absolute = {
                    "left": left + RELATIVE_ROI["left"],
                    "top": top + RELATIVE_ROI["top"],
                    "width": RELATIVE_ROI["width"],
                    "height": RELATIVE_ROI["height"]
                }
                
                with mss.mss() as sct:
                    raw = np.array(sct.grab(roi_absolute))
                roi_frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                print("Using fallback RELATIVE_ROI for scanning")

            # OCR inference on ROI
            result, _ = self.ocr(roi_frame)

            found_maps = set()

            for box, text, conf in result:
                best_match = None
                best_score = 0.0
                for known in self.known_maps:
                    score = Levenshtein.ratio(text.lower(), known.lower())
                    if score > 0.6 and score > best_score:
                        best_score = score
                        best_match = known
                if best_match:
                    found_maps.add(best_match)

            current_items = set(self.map_list.get_items())
            added = 0

            for m in found_maps:
                if m not in current_items:
                    self.map_list.add_item(m)
                    added += 1

            if added > 0:
                QMessageBox.information(self, "Scan Complete", f"Added {added} new maps.")
            else:
                QMessageBox.information(self, "Scan Complete", "No new maps found.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Scan failed:\n{e}")

    ##############################################
    # SCROLL ICON SETUP — unchanged
    ##############################################

    def setup_scroll_icon(self):
        win_rect = game_context.get_window_rect()
        if not win_rect:
            QMessageBox.warning(self, "Error", "Game window not found.")
            return

        try:
            win_left, win_top, win_right, win_bottom = win_rect
            win_width = win_right - win_left
            win_height = win_bottom - win_top

            # Capture full game window
            full_region = {
                "left": win_left,
                "top": win_top,
                "width": win_width,
                "height": win_height
            }

            with mss.mss() as sct:
                raw = np.array(sct.grab(full_region))
            full_frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

            roi_frame = None
            
            # Try YOLO detection first
            if self.yolo_model:
                try:
                    results = self.yolo_model(full_frame, verbose=False)
                    if len(results) > 0 and len(results[0].boxes) > 0:
                        box = results[0].boxes[0]
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        roi_frame = full_frame[y1:y2, x1:x2]
                        print(f"YOLO detected summon window for setup at: ({x1},{y1}) -> ({x2},{y2})")
                    else:
                        print("YOLO: No summon window detected during setup.")
                except Exception as e:
                    print(f"YOLO detection error during setup: {e}")

            # Fallback to RELATIVE_ROI
            if roi_frame is None:
                roi_left = win_left + RELATIVE_ROI["left"]
                roi_top = win_top + RELATIVE_ROI["top"]
                
                # Adjust to be relative to the captured full_frame for cropping
                # full_frame is (win_height, win_width)
                # RELATIVE_ROI is relative to win_left, win_top
                
                # We can just crop from full_frame using RELATIVE_ROI coords
                r_x = int(RELATIVE_ROI["left"])
                r_y = int(RELATIVE_ROI["top"])
                r_w = int(RELATIVE_ROI["width"])
                r_h = int(RELATIVE_ROI["height"])
                
                # Ensure bounds
                r_x = max(0, r_x)
                r_y = max(0, r_y)
                r_w = min(win_width - r_x, r_w)
                r_h = min(win_height - r_y, r_h)
                
                roi_frame = full_frame[r_y:r_y+r_h, r_x:r_x+r_w]
                print("Using fallback RELATIVE_ROI for setup")

            # Show ROI selection
            r = cv2.selectROI("Select Scroll Icon (ROI)", roi_frame, showCrosshair=True, fromCenter=False)
            cv2.destroyWindow("Select Scroll Icon (ROI)")

            if r == (0, 0, 0, 0):
                return

            x, y, w, h = r
            template = roi_frame[y:y+h, x:x+w]

            # Save to current directory for persistence (Issue 7)
            template_dir = os.path.join(os.getcwd(), "data", "templates")
            os.makedirs(template_dir, exist_ok=True)

            # Save as user-calibrated version
            cv2.imwrite(os.path.join(template_dir, "scroll_icon_user.png"), template)

            # Also save position for reference
            with open(os.path.join(template_dir, "scroll_icon_pos.json"), "w") as f:
                json.dump({"x": x, "y": y, "w": w, "h": h}, f)

            QMessageBox.information(self, "Success", "Scroll icon saved (persisted).")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to setup scroll icon:\n{e}")

    ##############################################

    def load_settings(self, data):
        self.map_list.set_state(data.get("map_list", []))
        # click_enabled is deprecated, always True
        self.num_channels = int(data.get("num_channels", 1))
        self.key_combo.setCurrentText(data.get("pelerynka_key", "F1"))
        self.preview_checkbox.setChecked(data.get("show_preview", True))

    def get_settings(self):
        return {
            "map_list": self.map_list.get_state(),
            # click_enabled removed
            # num_channels is now managed by SettingsPage
            "pelerynka_key": self.key_combo.currentText(),
            "show_preview": self.preview_checkbox.isChecked()
        }


##############################################
# OTHER TABS
##############################################

class MetinFarmingTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        msg = QLabel("Metin Farming UI will be added here.")
        msg.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg)
        self.setLayout(layout)


from gui.controllers.boss_tab_farming import BossTabManager

class BossFarmingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = BossTabManager()
        self.manager.frame_update.connect(self.update_preview)
        self.manager.status_update.connect(self.update_status)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Status Label
        self.status_label = QLabel("Status: Idle")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(self.status_label)

        # Preview Label
        self.preview_label = QLabel("Preview will appear here")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("background-color: #000; border: 1px solid #333;")
        layout.addWidget(self.preview_label)

        # Start/Stop Button
        self.toggle_btn = QPushButton("Start Detection")
        self.toggle_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.toggle_btn.clicked.connect(self.toggle_detection)
        layout.addWidget(self.toggle_btn)

        layout.addStretch()
        self.setLayout(layout)

    def toggle_detection(self):
        if self.toggle_btn.text() == "Start Detection":
            self.manager.start_detection()
            self.toggle_btn.setText("Stop Detection")
            self.toggle_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
            self.status_label.setText("Status: Starting...")
        else:
            self.stop_detection()

    def stop_detection(self):
        self.manager.stop_detection()
        self.toggle_btn.setText("Start Detection")
        self.toggle_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.status_label.setText("Status: Stopped")
        self.preview_label.setText("Preview stopped")
        self.preview_label.setPixmap(QPixmap())

    def update_status(self, status):
        self.status_label.setText(f"Status: {status}")

    def update_preview(self, frame):
        if frame is None:
            return
            
        # Convert numpy array (BGR) to QImage
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_BGR888)
        
        # Scale to fit label
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled_pixmap)

def combat_page(main_window=None):
    tabs = QTabWidget()
    tabs.addTab(TeleporterTab(main_window=main_window), "Boss Farming")
    tabs.addTab(BossFarmingTab(), "Metin Farming")
    return tabs
