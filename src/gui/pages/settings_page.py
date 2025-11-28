from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal, QObject
from pynput import keyboard


class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #1f1f1f;
                border: 1px solid #333;
                border-radius: 8px;
            }
        """)


class HotkeyListener(QObject):
    """Global hotkey listener using pynput."""
    emergency_stop_triggered = Signal()
    
    def __init__(self):
        super().__init__()
        self.listener = None
        self.hotkey_str = None
        self.target_key = None
        self.modifiers = set()
        self.pressed_modifiers = set()
        
    def set_hotkey(self, hotkey_str):
        """Set the hotkey combination from a string like 'F9' or 'ctrl+shift+q'."""
        # Stop existing listener
        self.stop()
        
        if not hotkey_str:
            return
        
        self.hotkey_str = hotkey_str.lower()
        
        # Parse the hotkey string
        parts = self.hotkey_str.split('+')
        
        # Separate modifiers from the main key
        self.modifiers = set()
        self.target_key = None
        
        for part in parts:
            part = part.strip()
            if part in ['ctrl', 'control']:
                self.modifiers.add(keyboard.Key.ctrl_l)
                self.modifiers.add(keyboard.Key.ctrl_r)
            elif part in ['shift']:
                self.modifiers.add(keyboard.Key.shift_l)
                self.modifiers.add(keyboard.Key.shift_r)
            elif part in ['alt']:
                self.modifiers.add(keyboard.Key.alt_l)
                self.modifiers.add(keyboard.Key.alt_r)
            else:
                # This is the main key
                self.target_key = part
        
        # Start the listener
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        print(f"HotkeyListener: Listening for '{hotkey_str}'")
    
    def _on_press(self, key):
        """Called when a key is pressed."""
        # Track modifiers
        if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, 
                   keyboard.Key.shift_l, keyboard.Key.shift_r,
                   keyboard.Key.alt_l, keyboard.Key.alt_r]:
            self.pressed_modifiers.add(key)
        
        # Check if this matches our target
        try:
            # Get the key name
            key_name = None
            if hasattr(key, 'name'):
                key_name = key.name.lower()
            elif hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
            
            if key_name == self.target_key:
                # Check if all required modifiers are pressed
                if self.modifiers.issubset(self.pressed_modifiers) or not self.modifiers:
                    self._on_activate()
        except Exception as e:
            pass
    
    def _on_release(self, key):
        """Called when a key is released."""
        # Untrack modifiers
        if key in self.pressed_modifiers:
            self.pressed_modifiers.discard(key)
    
    def _on_activate(self):
        """Called when the hotkey is pressed."""
        print(f"HotkeyListener: Panic button triggered!")
        self.emergency_stop_triggered.emit()
    
    def stop(self):
        """Stop the listener."""
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.pressed_modifiers.clear()


class SettingsPage(QWidget):
    """Settings page with emergency stop hotkey configuration."""
    emergency_stop = Signal()
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.hotkey_listener = HotkeyListener()
        self.hotkey_listener.emergency_stop_triggered.connect(self._handle_emergency_stop)
        self.init_ui()
    
    def init_ui(self):
        """Create the settings UI."""
        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(40, 10, 40, 30)
        page_layout.setSpacing(25)

        card = Card()
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # --- Title ---
        title = QLabel("Settings")
        title.setStyleSheet("color: #cccccc; font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title)

        # --- Emergency Stop Hotkey ---
        hotkey_label = QLabel("Emergency Stop Hotkey:")
        hotkey_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        card_layout.addWidget(hotkey_label)

        hotkey_layout = QHBoxLayout()
        
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("e.g. F9, ctrl+shift+q")
        self.hotkey_input.setText("F9")  # Default
        self.hotkey_input.setStyleSheet("""
            QLineEdit {
                background: #2b2b2b;
                color: white;
                padding: 8px 10px;
                border-radius: 6px;
                border: 1px solid #444;
            }
            QLineEdit:focus {
                border: 1px solid #5e9cff;
            }
        """)
        hotkey_layout.addWidget(self.hotkey_input)

        self.apply_hotkey_btn = QPushButton("Apply")
        self.apply_hotkey_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a3a;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #555;
            }
            QPushButton:hover { background: #474747; }
            QPushButton:pressed { background: #323232; }
        """)
        self.apply_hotkey_btn.clicked.connect(self.apply_hotkey)
        hotkey_layout.addWidget(self.apply_hotkey_btn)

        card_layout.addLayout(hotkey_layout)

        # --- Info ---
        info_label = QLabel(
            "Set a global hotkey to stop all bot functions immediately.\n"
            "Format: key or modifier+key (e.g., F9, ctrl+shift+q)\n"
            "Modifiers: ctrl, shift, alt"
        )
        info_label.setStyleSheet("color: #888888; font-size: 11px;")
        info_label.setAlignment(Qt.AlignLeft)
        card_layout.addWidget(info_label)

        # --- Status ---
        self.status_label = QLabel("Status: No hotkey set")
        self.status_label.setStyleSheet("color: #888888; font-size: 12px;")
        card_layout.addWidget(self.status_label)

        card_layout.addStretch()
        card.setLayout(card_layout)

        page_layout.addWidget(card)
        page_layout.addStretch()

        self.setLayout(page_layout)
        self.setStyleSheet("background-color: #151515;")
    
    def apply_hotkey(self):
        """Apply the configured hotkey."""
        hotkey = self.hotkey_input.text().strip()
        if hotkey:
            try:
                self.hotkey_listener.set_hotkey(hotkey)
                self.status_label.setText(f"Status: Listening for '{hotkey}'")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
            except Exception as e:
                self.status_label.setText(f"Status: Error - {e}")
                self.status_label.setStyleSheet("color: #f44336; font-size: 12px;")
                print(f"Error setting hotkey: {e}")
        else:
            self.hotkey_listener.stop()
            self.status_label.setText("Status: No hotkey set")
            self.status_label.setStyleSheet("color: #888888; font-size: 12px;")
    
    def _handle_emergency_stop(self):
        """Handle emergency stop signal."""
        print("PANIC BUTTON TRIGGERED")
        self.emergency_stop.emit()
        
        # Stop all running workers
        if self.main_window:
            # Stop combat page workers
            if hasattr(self.main_window, 'combat_page'):
                combat_page = self.main_window.combat_page
                if hasattr(combat_page, 'stop_detection'):
                    combat_page.stop_detection()
                    print("Stopped boss farming")
    
    def cleanup(self):
        """Clean up the hotkey listener."""
        self.hotkey_listener.stop()

    def get_settings(self):
        """Return settings for profile saving."""
        return {
            "emergency_hotkey": self.hotkey_input.text()
        }

    def load_settings(self, data):
        """Load settings from profile data."""
        hotkey = data.get("emergency_hotkey", "F9")
        self.hotkey_input.setText(hotkey)
        self.apply_hotkey()