"""
Settings page for configuring hotkeys and other bot settings.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QGroupBox, QComboBox, QSpinBox, QCheckBox, QScrollArea, QSizePolicy, QGridLayout
)
from PySide6.QtCore import Qt


class SettingsPage(QWidget):
    """Settings page for configuring bot parameters."""

    def __init__(self):
        super().__init__()
        self.farming_manager = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)

        # Create scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Channel hotkeys section
        scroll_layout.addWidget(self._create_channel_hotkeys_section())

        # Add stretch at the end
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area, 1)

        self.setLayout(main_layout)

    def _create_channel_hotkeys_section(self) -> QGroupBox:
        """Create the channel hotkeys configuration section."""
        group = QGroupBox("Channel Hotkeys")
        layout = QVBoxLayout()

        # Info label
        info_label = QLabel(
            "Configure keyboard shortcuts for each channel. "
            "Leave modifier empty for just the key, or select 'shift', 'ctrl', or 'alt'."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(info_label)

        # Grid for channel hotkeys
        grid = QGridLayout()
        grid.setSpacing(10)

        # Header row
        grid.addWidget(QLabel("Channel"), 0, 0)
        grid.addWidget(QLabel("Key"), 0, 1)
        grid.addWidget(QLabel("Modifier"), 0, 2)

        self.channel_hotkey_widgets = {}  # Store references to combo boxes

        # Create rows for each channel (1-12)
        for channel in range(1, 13):
            row = channel

            # Channel number label
            grid.addWidget(QLabel(f"Channel {channel}"), row, 0)

            # Key combo box
            key_combo = QComboBox()
            key_combo.addItems(["F1", "F2", "F3", "F4", "F5", "F6",
                                "F7", "F8", "F9", "F10", "F11", "F12"])
            key_combo.setCurrentText(f"F{channel}" if channel <= 6 else "F1")
            grid.addWidget(key_combo, row, 1)

            # Modifier combo box
            modifier_combo = QComboBox()
            modifier_combo.addItems(["(none)", "shift", "ctrl", "alt"])
            modifier_combo.setCurrentText("shift" if channel <= 6 else "(none)")
            grid.addWidget(modifier_combo, row, 2)

            self.channel_hotkey_widgets[channel] = {
                'key': key_combo,
                'modifier': modifier_combo
            }

        layout.addLayout(grid)

        # Buttons
        button_layout = QHBoxLayout()

        self.btn_save = QPushButton("Save Hotkey Settings")
        self.btn_save.clicked.connect(self._on_save_hotkeys)
        button_layout.addWidget(self.btn_save)

        self.btn_reset = QPushButton("Reset to Defaults")
        self.btn_reset.clicked.connect(self._on_reset_hotkeys)
        button_layout.addWidget(self.btn_reset)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def set_farming_manager(self, manager):
        """Set the farming manager instance."""
        self.farming_manager = manager
        self._load_hotkey_settings()

    def _load_hotkey_settings(self):
        """Load current hotkey settings from config."""
        if not self.farming_manager:
            return

        config = self.farming_manager.config_manager.get_boss_config()
        channel_hotkeys = config.get("channel_hotkeys", [])

        # Create a dict for easy lookup
        hotkey_dict = {ch['channel']: ch for ch in channel_hotkeys}

        # Update UI with current settings
        for channel in range(1, 13):
            if channel in hotkey_dict:
                hotkey = hotkey_dict[channel]
                key = hotkey.get('key', f'F{channel}')
                modifier = hotkey.get('modifier') or '(none)'

                self.channel_hotkey_widgets[channel]['key'].setCurrentText(key)
                self.channel_hotkey_widgets[channel]['modifier'].setCurrentText(
                    modifier if modifier != '(none)' and modifier else "(none)"
                )

    def _on_save_hotkeys(self):
        """Save the configured hotkeys to config."""
        if not self.farming_manager:
            return

        # Build channel_hotkeys list
        channel_hotkeys = []
        for channel in range(1, 13):
            key = self.channel_hotkey_widgets[channel]['key'].currentText()
            modifier = self.channel_hotkey_widgets[channel]['modifier'].currentText()

            # Convert "(none)" to empty/None
            if modifier == "(none)":
                modifier = None

            channel_hotkeys.append({
                'channel': channel,
                'key': key,
                'modifier': modifier
            })

        # Update config
        config = self.farming_manager.config_manager.get_boss_config()
        config['channel_hotkeys'] = channel_hotkeys
        self.farming_manager.config_manager.update_boss_config(config)

        # Show confirmation
        print("Channel hotkeys saved successfully!")
        self._load_hotkey_settings()  # Reload to confirm

    def _on_reset_hotkeys(self):
        """Reset hotkeys to default values."""
        if not self.farming_manager:
            return

        # Reset to defaults: F1-F6 with shift modifier
        default_hotkeys = []
        for channel in range(1, 13):
            if channel <= 6:
                default_hotkeys.append({
                    'channel': channel,
                    'key': f'F{channel}',
                    'modifier': 'shift'
                })
            else:
                default_hotkeys.append({
                    'channel': channel,
                    'key': 'F1',
                    'modifier': None
                })

        # Update config
        config = self.farming_manager.config_manager.get_boss_config()
        config['channel_hotkeys'] = default_hotkeys
        self.farming_manager.config_manager.update_boss_config(config)

        # Reload UI
        self._load_hotkey_settings()
        print("Channel hotkeys reset to defaults!")
