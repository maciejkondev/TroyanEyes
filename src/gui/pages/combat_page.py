"""
Combat page with Boss and Metin farming features.
Provides UI controls for starting/stopping automation, live preview, and status monitoring.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
    QLabel, QScrollArea, QSizePolicy, QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QSlider
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QImage
import cv2
import numpy as np
import os


class CombatPage(QWidget):
    """Main combat farming page with tabs for Boss and Metin farming."""

    def __init__(self):
        super().__init__()
        self.boss_worker = None
        self.farming_manager = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Combat Farming")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)

        # Tab widget for Boss and Metin
        self.tabs = QTabWidget()
        self.boss_tab = BossFarmingTab()
        self.metin_tab = MetinFarmingTab()

        self.tabs.addTab(self.boss_tab, "Template based Boss Farming")
        self.tabs.addTab(self.metin_tab, "Metin Farming")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def set_farming_manager(self, manager):
        """Set the farming manager instance."""
        self.farming_manager = manager
        self.boss_tab.set_farming_manager(manager)
        self.metin_tab.set_farming_manager(manager)

    def cleanup(self):
        """Clean up when page is closed."""
        self.boss_tab.stop_farming()
        self.metin_tab.stop_farming()


class BossFarmingTab(QWidget):
    """Tab for boss farming controls and monitoring."""

    def __init__(self):
        super().__init__()
        self.farming_manager = None
        self.boss_worker = None
        self.hotkey_listener = None
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self._update_preview)
        self.init_ui()

    def init_ui(self):
        """Initialize the boss farming tab UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- CONTROL SECTION ---
        control_section = self._create_control_section()
        main_layout.addWidget(control_section)

        # --- PREVIEW SECTION ---
        preview_section = self._create_preview_section()
        main_layout.addWidget(preview_section, 1)

        # --- STATUS/LOG SECTION ---
        status_section = self._create_status_section()
        main_layout.addWidget(status_section)

        self.setLayout(main_layout)
        
        # Connect hotkey checkbox
        if hasattr(self, 'hotkey_enabled'):
            self.hotkey_enabled.toggled.connect(self._setup_hotkeys)

    def _create_control_section(self) -> QGroupBox:
        """Create the control buttons and settings section."""
        group = QGroupBox("Controls")
        layout = QVBoxLayout()

        # Top row: Start/Stop/Pause/Reset buttons
        button_layout = QHBoxLayout()

        self.btn_start = QPushButton("Start Farming")
        self.btn_start.clicked.connect(self.start_farming)
        button_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop Farming")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_farming)
        button_layout.addWidget(self.btn_stop)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.pause_farming)
        button_layout.addWidget(self.btn_pause)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(self.reset_farming)
        button_layout.addWidget(self.btn_reset)

        # Region selection button
        self.btn_set_region = QPushButton("Set Region")
        self.btn_set_region.setToolTip("Select screen region to scan (full-screen selector)")
        self.btn_set_region.clicked.connect(self._on_set_region_clicked)
        button_layout.addWidget(self.btn_set_region)

        layout.addLayout(button_layout)

        # Second row: Settings
        settings_layout = QHBoxLayout()

        # Template selector
        settings_layout.addWidget(QLabel("Template:"))
        self.template_label = QLabel("dostepny_template.png")
        self.template_label.setStyleSheet("color: gray;")
        settings_layout.addWidget(self.template_label)

        # Channel settings
        settings_layout.addWidget(QLabel("Channels:"))
        self.channels_spin = QSpinBox()
        self.channels_spin.setMinimum(1)
        self.channels_spin.setMaximum(12)
        self.channels_spin.setValue(6)
        settings_layout.addWidget(self.channels_spin)

        # Check speed setting (loop_delay)
        settings_layout.addWidget(QLabel("Check Speed:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(10)  # 10ms minimum
        self.speed_slider.setMaximum(500)  # 500ms maximum
        self.speed_slider.setValue(100)  # 100ms default
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(100)
        self.speed_slider.setMaximumWidth(150)
        self.speed_slider.setToolTip(
            "Lower = faster checks, higher CPU usage\n"
            "Higher = slower checks, lower CPU usage"
        )
        settings_layout.addWidget(self.speed_slider)
        
        self.speed_label = QLabel("100ms")
        self.speed_label.setMinimumWidth(50)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        settings_layout.addWidget(self.speed_label)
        
        # Help icon for speed
        speed_help = QLabel("?")
        speed_help.setStyleSheet(
            "background-color: #555; color: #fff; "
            "border-radius: 8px; width: 16px; height: 16px; "
            "text-align: center; font-weight: bold; font-size: 12px;"
        )
        speed_help.setFixedSize(16, 16)
        speed_help.setToolTip(
            "Controls how often the bot checks for 'Dostępny' and clicks:\n"
            "• 10-50ms = Very fast, high CPU usage\n"
            "• 50-150ms = Balanced (recommended)\n"
            "• 150ms+ = Slower, low CPU usage"
        )
        settings_layout.addWidget(speed_help)

        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        # Third row: Hotkey settings
        hotkey_layout = QHBoxLayout()
        
        self.hotkey_enabled = QCheckBox("Enable Hotkeys")
        self.hotkey_enabled.setChecked(False)
        hotkey_layout.addWidget(self.hotkey_enabled)
        
        hotkey_layout.addWidget(QLabel("Start:"))
        self.hotkey_start_combo = QComboBox()
        self.hotkey_start_combo.addItems(self._get_available_keys())
        self.hotkey_start_combo.setCurrentText("F9")
        hotkey_layout.addWidget(self.hotkey_start_combo)
        
        hotkey_layout.addWidget(QLabel("Stop:"))
        self.hotkey_stop_combo = QComboBox()
        self.hotkey_stop_combo.addItems(self._get_available_keys())
        self.hotkey_stop_combo.setCurrentText("F10")
        hotkey_layout.addWidget(self.hotkey_stop_combo)
        
        hotkey_layout.addWidget(QLabel("Pause:"))
        self.hotkey_pause_combo = QComboBox()
        self.hotkey_pause_combo.addItems(self._get_available_keys())
        self.hotkey_pause_combo.setCurrentText("F11")
        hotkey_layout.addWidget(self.hotkey_pause_combo)
        
        hotkey_layout.addWidget(QLabel("Reset:"))
        self.hotkey_reset_combo = QComboBox()
        self.hotkey_reset_combo.addItems(self._get_available_keys())
        self.hotkey_reset_combo.setCurrentText("F12")
        hotkey_layout.addWidget(self.hotkey_reset_combo)
        
        hotkey_layout.addStretch()
        layout.addLayout(hotkey_layout)

        group.setLayout(layout)
        return group

    def _create_preview_section(self) -> QGroupBox:
        """Create the live preview section."""
        group = QGroupBox("Live Preview")
        layout = QVBoxLayout()

        # Toggle button for preview
        toggle_layout = QHBoxLayout()
        self.btn_toggle_preview = QPushButton("Hide Preview")
        self.btn_toggle_preview.setMaximumWidth(120)
        self.btn_toggle_preview.clicked.connect(self._toggle_preview)
        toggle_layout.addWidget(self.btn_toggle_preview)
        toggle_layout.addStretch()
        layout.addLayout(toggle_layout)

        # Preview display (full size when visible, not resizable)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #222; border: 1px solid #444;")
        self.preview_label.setText("No preview available")
        self.preview_visible = True

        layout.addWidget(self.preview_label, 1)
        group.setLayout(layout)
        return group

    def _create_status_section(self) -> QGroupBox:
        """Create the status and logging section."""
        group = QGroupBox("Status")
        layout = QVBoxLayout()

        # Status display
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("State:"))
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        status_layout.addWidget(self.status_label)

        # Activity indicator
        status_layout.addWidget(QLabel("Activity:"))
        self.activity_label = QLabel("●")
        self.activity_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.activity_label)

        # Stats
        self.stats_label = QLabel("Targets found: 0 | Channels cycled: 0 | Swaps: 0")
        self.stats_label.setStyleSheet("color: #888; font-size: 10px;")

        status_layout.addWidget(self.stats_label)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        # Log area
        self.log_label = QLabel("Waiting to start...")
        self.log_label.setWordWrap(True)
        self.log_label.setStyleSheet("color: #ccc; font-family: monospace; font-size: 9px;")
        layout.addWidget(self.log_label)

        group.setLayout(layout)
        return group

    def set_farming_manager(self, manager):
        """Set the farming manager instance."""
        self.farming_manager = manager
        self._setup_hotkeys()

    def _get_available_keys(self):
        """Get list of available F-keys for hotkey selection."""
        from gui.controllers.hotkey_listener import HotkeyListener
        return HotkeyListener.get_available_keys()

    def _setup_hotkeys(self):
        """Initialize hotkey listener if enabled."""
        from gui.controllers.hotkey_listener import HotkeyListener
        
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        
        if not self.hotkey_enabled.isChecked():
            return
        
        # Create hotkey config from UI
        hotkey_config = {
            "enabled": True,
            "start": self.hotkey_start_combo.currentText(),
            "stop": self.hotkey_stop_combo.currentText(),
            "pause": self.hotkey_pause_combo.currentText(),
            "reset": self.hotkey_reset_combo.currentText(),
        }
        
        self.hotkey_listener = HotkeyListener(hotkey_config)
        self.hotkey_listener.hotkey_triggered.connect(self._handle_hotkey)
        self.hotkey_listener.status_changed.connect(self._on_hotkey_status)
        self.hotkey_listener.start()
        self._log("Hotkeys enabled")

    def _handle_hotkey(self, action: str):
        """Handle hotkey trigger from listener."""
        if action == "start":
            self.start_farming()
        elif action == "stop":
            self.stop_farming()
        elif action == "pause":
            self.pause_farming()
        elif action == "reset":
            self.reset_farming()

    def _on_hotkey_status(self, message: str):
        """Handle hotkey status messages."""
        self._log(f"[Hotkey] {message}")

    def _on_set_region_clicked(self):
        """Open full-screen region selector and persist selected region."""
        try:
            from gui.widgets.region_selector import RegionSelector
        except Exception as e:
            self._log(f"Region selector not available: {e}")
            return

        self.selector = RegionSelector(self.window())
        self.selector.region_selected.connect(self._on_region_selected)
        self.selector.cancelled.connect(lambda: self._log("Region selection cancelled"))
        self.selector.show()

    def _on_region_selected(self, rect):
        """Handle region selected by user (QRect in global coords)."""
        left, top, w, h = rect.left(), rect.top(), rect.width(), rect.height()
        self._log(f"Region selected: {left},{top},{w},{h}")

        # Persist to config
        if self.farming_manager:
            try:
                cfg_mgr = self.farming_manager.get_config_manager()
                cfg_mgr.update_boss_config({"region": [left, top, w, h]})
                self._log("Saved region to configuration")
            except Exception as e:
                self._log(f"Failed to save config: {e}")

        # Update running worker if present
        if self.boss_worker and hasattr(self.boss_worker, 'config'):
            try:
                self.boss_worker.config['region'] = (left, top, w, h)
                self._log("Updated running worker region")
            except Exception as e:
                self._log(f"Failed to update worker region: {e}")

    def start_farming(self):
        """Start boss farming."""
        if not self.farming_manager:
            self._log("ERROR: Farming manager not initialized")
            return

        try:
            self.boss_worker = self.farming_manager.start_boss_farming()
            if self.boss_worker is None:
                self._log("ERROR: Could not start farming worker")
                return

            # Connect signals
            self.boss_worker.status_changed.connect(self._on_status_changed)
            self.boss_worker.frame_captured.connect(self._on_frame_captured)
            self.boss_worker.target_found.connect(self._on_target_found)
            self.boss_worker.target_lost.connect(self._on_target_lost)
            self.boss_worker.stats_updated.connect(self._on_stats_updated)

            # Update UI state
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.btn_pause.setEnabled(True)
            self.btn_reset.setEnabled(True)
            self.status_label.setText("Running")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")

            # Setup and start hotkey listener for channel switching
            self._setup_channel_hotkeys()

            # Start preview timer
            self.preview_timer.start(100)  # Update every 100ms

            self._log("Boss farming started")

        except Exception as e:
            self._log(f"ERROR: {str(e)}")

    def stop_farming(self):
        """Stop boss farming."""
        if self.boss_worker:
            self.farming_manager.stop_boss_farming()
            self.boss_worker = None

        # Stop channel hotkey listener
        if self.farming_manager and self.farming_manager.hotkey_listener:
            self.farming_manager.hotkey_listener.stop()
            self.farming_manager.hotkey_listener = None

        self.preview_timer.stop()

        # Update UI state
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_reset.setEnabled(False)
        self.status_label.setText("Idle")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")

        self._log("Boss farming stopped")

    def pause_farming(self):
        """Pause/Resume farming."""
        if self.boss_worker:
            if self.boss_worker.paused:
                self.boss_worker.resume()
                self.btn_pause.setText("Pause")
                self.status_label.setText("Running")
            else:
                self.boss_worker.pause()
                self.btn_pause.setText("Resume")
                self.status_label.setText("Paused")

    def reset_farming(self):
        """Reset farming state."""
        if self.boss_worker:
            self.boss_worker.reset()
            self._log("Farming state reset")

    def _on_threshold_changed(self, value: int):
        """Handle threshold slider change."""
        # Convert slider value (0-100) to threshold (0.0-1.0)
        threshold = value / 100.0
        self.threshold_label.setText(f"{threshold:.2f}")
        
        # Update running worker config if present
        if self.boss_worker:
            self.boss_worker.config['match_threshold'] = threshold

    def _on_speed_changed(self, value: int):
        """Handle check speed slider change."""
        # Slider value is already in milliseconds
        self.speed_label.setText(f"{value}ms")
        
        # Update running worker config if present
        if self.boss_worker:
            self.boss_worker.config['loop_delay'] = value / 1000.0  # Convert to seconds

    def _on_status_changed(self, message: str):
        """Handle status change from worker."""
        self._log(message)

    def _on_frame_captured(self, frame: np.ndarray):
        """Handle frame capture from worker."""
        self.last_frame = frame

    def _on_target_found(self):
        """Handle target found."""
        self.activity_label.setText("●")
        self.activity_label.setStyleSheet("color: green;")

    def _on_target_lost(self):
        """Handle target lost."""
        self.activity_label.setText("●")
        self.activity_label.setStyleSheet("color: red;")

    def _on_stats_updated(self, stats: dict):
        """Handle stats update from worker."""
        targets = stats.get("targets_found", 0)
        channels = stats.get("channels_cycled", 0)
        swaps = stats.get("swaps_performed", 0)
        self.stats_label.setText(f"Targets found: {targets} | Channels cycled: {channels} | Swaps: {swaps}")

    def _update_preview(self):
        """Update the preview image."""
        if hasattr(self, "last_frame") and self.last_frame is not None:
            frame = self.last_frame
            # Resize to fit preview area
            frame_resized = cv2.resize(frame, (300, 250))
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            # Convert to QImage
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(
                frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888
            )
            # Set to label
            self.preview_label.setPixmap(QPixmap.fromImage(qt_image))
    def _toggle_preview(self):
        """Toggle preview visibility."""
        self.preview_visible = not self.preview_visible
        self.preview_label.setVisible(self.preview_visible)
        self.btn_toggle_preview.setText("Hide Preview" if self.preview_visible else "Show Preview")
        if not self.preview_visible:
            self.preview_timer.stop()
        elif self.boss_worker and self.boss_worker.running:
            self.preview_timer.start(100)


    def _log(self, message: str):
        """Add message to log."""
        current_log = self.log_label.text()
        lines = current_log.split("\n")
        lines.append(message)
        # Keep only last 10 lines
        if len(lines) > 10:
            lines = lines[-10:]
        self.log_label.setText("\n".join(lines))


class MetinFarmingTab(QWidget):
    """Tab for metin farming controls and monitoring."""

    def __init__(self):
        super().__init__()
        self.farming_manager = None
        self.hotkey_listener = None
        self.init_ui()

    def init_ui(self):
        """Initialize the metin farming tab UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Hotkey controls (like boss tab)
        hotkey_group = QGroupBox("Hotkey Controls")
        hotkey_layout = QHBoxLayout()
        
        self.hotkey_enabled = QCheckBox("Enable Hotkeys")
        self.hotkey_enabled.setChecked(False)
        hotkey_layout.addWidget(self.hotkey_enabled)
        
        hotkey_layout.addWidget(QLabel("Start:"))
        self.hotkey_start_combo = QComboBox()
        self.hotkey_start_combo.addItems(self._get_available_keys())
        self.hotkey_start_combo.setCurrentText("F5")
        hotkey_layout.addWidget(self.hotkey_start_combo)
        
        hotkey_layout.addWidget(QLabel("Stop:"))
        self.hotkey_stop_combo = QComboBox()
        self.hotkey_stop_combo.addItems(self._get_available_keys())
        self.hotkey_stop_combo.setCurrentText("F6")
        hotkey_layout.addWidget(self.hotkey_stop_combo)
        
        hotkey_layout.addWidget(QLabel("Pause:"))
        self.hotkey_pause_combo = QComboBox()
        self.hotkey_pause_combo.addItems(self._get_available_keys())
        self.hotkey_pause_combo.setCurrentText("F7")
        hotkey_layout.addWidget(self.hotkey_pause_combo)
        
        hotkey_layout.addWidget(QLabel("Reset:"))
        self.hotkey_reset_combo = QComboBox()
        self.hotkey_reset_combo.addItems(self._get_available_keys())
        self.hotkey_reset_combo.setCurrentText("F8")
        hotkey_layout.addWidget(self.hotkey_reset_combo)
        
        hotkey_layout.addStretch()
        hotkey_group.setLayout(hotkey_layout)
        main_layout.addWidget(hotkey_group)

        # Placeholder content
        placeholder = QLabel("Metin Farming - Coming Soon")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("font-size: 16px; color: #888;")
        main_layout.addWidget(placeholder)

        # Feature description
        features = QLabel(
            "Metin farming automation will include:\n"
            "• Automatic metin detection and clicking\n"
            "• Multi-channel support\n"
            "• Configurable patterns and intervals"
        )
        features.setAlignment(Qt.AlignCenter)
        features.setStyleSheet("color: #666; font-size: 12px;")
        main_layout.addWidget(features)

        main_layout.addStretch()
        self.setLayout(main_layout)
        
        # Connect hotkey checkbox
        self.hotkey_enabled.toggled.connect(self._setup_hotkeys)

    def _get_available_keys(self):
        """Get list of available F-keys for hotkey selection."""
        from gui.controllers.hotkey_listener import HotkeyListener
        return HotkeyListener.get_available_keys()

    def _setup_hotkeys(self):
        """Initialize hotkey listener if enabled."""
        from gui.controllers.hotkey_listener import HotkeyListener
        
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        
        if not self.hotkey_enabled.isChecked():
            return
        
        # Create hotkey config from UI
        hotkey_config = {
            "enabled": True,
            "start": self.hotkey_start_combo.currentText(),
            "stop": self.hotkey_stop_combo.currentText(),
            "pause": self.hotkey_pause_combo.currentText(),
            "reset": self.hotkey_reset_combo.currentText(),
        }
        
        self.hotkey_listener = HotkeyListener(hotkey_config)
        self.hotkey_listener.hotkey_triggered.connect(self._handle_hotkey)
        self.hotkey_listener.start()

    def _handle_hotkey(self, action: str):
        """Handle hotkey trigger from listener."""
        if action == "start":
            print("Metin: Start (not implemented)")
        elif action == "stop":
            print("Metin: Stop (not implemented)")
        elif action == "pause":
            print("Metin: Pause (not implemented)")
        elif action == "reset":
            print("Metin: Reset (not implemented)")

    def set_farming_manager(self, manager):
        """Set the farming manager instance."""
        self.farming_manager = manager

    def _setup_channel_hotkeys(self):
        """Setup hotkey listener for channel switching."""
        from gui.controllers.hotkey_listener import HotkeyListener
        
        if not self.farming_manager:
            return
        
        # Stop previous listener if any
        if self.farming_manager.hotkey_listener:
            self.farming_manager.hotkey_listener.stop()
        
        # Get channel hotkeys from config
        config = self.farming_manager.config_manager.get_boss_config()
        channel_hotkeys = config.get("channel_hotkeys", [])
        
        if not channel_hotkeys:
            self._log("No channel hotkeys configured")
            return
        
        # Create hotkey listener config with channel hotkeys
        hotkey_config = {
            "enabled": True,
            "channel_hotkeys": channel_hotkeys
        }
        
        # Create and start listener
        self.farming_manager.hotkey_listener = HotkeyListener(hotkey_config)
        self.farming_manager.hotkey_listener.channel_hotkey_triggered.connect(
            self._on_channel_hotkey
        )
        self.farming_manager.hotkey_listener.status_changed.connect(self._on_hotkey_status)
        self.farming_manager.hotkey_listener.start()
        
        self._log(f"Channel hotkeys enabled: {len(channel_hotkeys)} channels configured")

    def _on_channel_hotkey(self, channel: int):
        """Handle channel hotkey trigger."""
        self._log(f"Channel hotkey: switching to channel {channel}")
        if self.farming_manager:
            self.farming_manager.switch_to_channel(channel)

    def _on_hotkey_status(self, message: str):
        """Handle hotkey status messages."""
        self._log(f"[Hotkey] {message}")

    def stop_farming(self):
        """Stop metin farming (placeholder)."""
        pass
