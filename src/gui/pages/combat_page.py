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
                    teleporter.load_settings(data.get("teleporter", {}))

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
    def __init__(self):
        super().__init__()
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

        # Buttons
        btn_layout = QHBoxLayout()

        btn_scan = QPushButton("Scan Available Maps (OCR)")
        btn_scan.clicked.connect(self.scan_maps)
        btn_layout.addWidget(btn_scan)

        self.click_checkbox = QCheckBox("Click on Found Map")
        btn_layout.addWidget(self.click_checkbox)

        # Channel Count Input
        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 8)
        self.channel_spin.setValue(1)
        self.channel_spin.setPrefix("Channels: ")
        self.channel_spin.setStyleSheet("""
            QSpinBox {
                background: #2b2b2b;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 4px;
            }
        """)
        btn_layout.addWidget(self.channel_spin)



        # Pelerynka Key Selection
        lbl_cape = QLabel("Summoning Cape Key:")
        btn_layout.addWidget(lbl_cape)
        self.key_combo = QComboBox()
        self.key_combo.addItems(["F1", "F2", "F3", "F4"])
        self.key_combo.setCurrentText("F1")
        self.key_combo.setStyleSheet("""
            QComboBox {
                background: #2b2b2b;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        btn_layout.addWidget(self.key_combo)

        btn_select_icon = QPushButton("Setup Scroll Icon")
        btn_select_icon.clicked.connect(self.setup_scroll_icon)
        btn_layout.addWidget(btn_select_icon)

        self.preview_checkbox = QCheckBox("Show Preview")
        self.preview_checkbox.setChecked(True)
        btn_layout.addWidget(self.preview_checkbox)

        self.toggle_btn = QPushButton("Start Detection")
        self.toggle_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.toggle_btn.clicked.connect(self.toggle_farming)
        btn_layout.addWidget(self.toggle_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()
        self.setLayout(layout)

    def toggle_farming(self):
        if self.toggle_btn.text() == "Start Detection":
            priority_list = self.map_list.get_checked_items()
            click_enabled = self.click_checkbox.isChecked()
            num_channels = self.channel_spin.value()
            pelerynka_key = self.key_combo.currentText()
            show_preview = self.preview_checkbox.isChecked()
            print(f"Starting with priority: {priority_list}, click_enabled: {click_enabled}, channels: {num_channels}, key: {pelerynka_key}, preview: {show_preview}")
            
            self.manager.start_boss_farming(priority_list, click_enabled=click_enabled, num_channels=num_channels, pelerynka_key=pelerynka_key, show_preview=show_preview)
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
            win_left, win_top, _, _ = win_rect

            roi_left = win_left + RELATIVE_ROI["left"]
            roi_top = win_top + RELATIVE_ROI["top"]

            roi_region = {
                "top": int(roi_top),
                "left": int(roi_left),
                "width": int(RELATIVE_ROI["width"]),
                "height": int(RELATIVE_ROI["height"]),
            }

            with mss.mss() as sct:
                screenshot = np.array(sct.grab(roi_region))
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

            r = cv2.selectROI("Select Scroll Icon (ROI)", screenshot, showCrosshair=True, fromCenter=False)
            cv2.destroyWindow("Select Scroll Icon (ROI)")

            if r == (0, 0, 0, 0):
                return

            x, y, w, h = r
            template = screenshot[y:y+h, x:x+w]

            template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "templates"))
            os.makedirs(template_dir, exist_ok=True)

            cv2.imwrite(os.path.join(template_dir, "scroll_icon.png"), template)

            with open(os.path.join(template_dir, "scroll_icon_pos.json"), "w") as f:
                json.dump({"x": x, "y": y, "w": w, "h": h}, f)

            QMessageBox.information(self, "Success", "Scroll icon saved.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to setup scroll icon:\n{e}")

    ##############################################

    def load_settings(self, data):
        self.map_list.set_state(data.get("map_list", []))
        self.click_checkbox.setChecked(data.get("click_enabled", False))
        self.channel_spin.setValue(data.get("num_channels", 1))
        self.key_combo.setCurrentText(data.get("pelerynka_key", "F1"))
        self.preview_checkbox.setChecked(data.get("show_preview", True))

    def get_settings(self):
        return {
            "map_list": self.map_list.get_state(),
            "click_enabled": self.click_checkbox.isChecked(),
            "num_channels": self.channel_spin.value(),
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
