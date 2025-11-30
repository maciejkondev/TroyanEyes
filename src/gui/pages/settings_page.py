from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QHBoxLayout, QFrame, QSpinBox,
    QGridLayout, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
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
        
        # Initialize channel inputs dictionary before init_ui
        self.channel_inputs = {}
        
        self.init_ui()
    
    def init_ui(self):
        """Create the settings UI."""
        # Main layout for the page
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #151515;
            }
            QScrollBar:vertical {
                border: none;
                background: #2b2b2b;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        # Content Widget for Scroll Area
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #151515;")
        page_layout = QVBoxLayout(content_widget)
        page_layout.setContentsMargins(40, 20, 40, 30)
        page_layout.setSpacing(25)

        card = Card()
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # --- Title ---
        title = QLabel("Settings")
        title.setStyleSheet("color: #cccccc; font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title)

        # --- Panic Button (Renamed from Emergency Stop) ---
        hotkey_label = QLabel("Panic Button:")
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
                border: none;
            }

            QLineEdit:focus {
                background: #333333;
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

        # Info for Panic Button
        panic_info = QLabel(
            "Set a global hotkey to stop all bot functions immediately.\n"
            "Format: key or modifier+key (e.g., F9, ctrl+shift+q)\n"
            "Modifiers: ctrl, shift, alt"
        )
        panic_info.setStyleSheet("color: #888888; font-size: 11px;")
        panic_info.setAlignment(Qt.AlignLeft)
        card_layout.addWidget(panic_info)

        # --- Status ---
        self.status_label = QLabel("Status: Listening for 'F9'")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
        card_layout.addWidget(self.status_label)

        # --- Channel Settings ---
        channel_group_label = QLabel("Channel Configuration:")
        channel_group_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 10px;")
        card_layout.addWidget(channel_group_label)

        # Channel Count
        count_layout = QHBoxLayout()
        count_lbl = QLabel("Number of Channels:")
        count_lbl.setStyleSheet("color: #aaaaaa;")
        
        self.channel_count_spin = QSpinBox()
        self.channel_count_spin.setRange(1, 16)
        self.channel_count_spin.setValue(1)
        self.channel_count_spin.setStyleSheet("""
            QSpinBox {
                background: #2b2b2b;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 4px;
                min-width: 60px;
            }
        """)
        self.channel_count_spin.valueChanged.connect(self.update_channel_inputs)
        
        count_layout.addWidget(count_lbl)
        count_layout.addWidget(self.channel_count_spin)
        count_layout.addStretch()
        card_layout.addLayout(count_layout)

        # Channel Hotkeys Container
        self.channel_inputs = {}
        self.channels_container = QWidget()
        self.channels_layout = QGridLayout(self.channels_container)
        self.channels_layout.setSpacing(10)
        self.channels_layout.setContentsMargins(0, 10, 0, 0)
        card_layout.addWidget(self.channels_container)
        
        # Initialize with default 1 channel
        self.update_channel_inputs(1)

        # Channel info
        channel_info = QLabel("Channel Hotkeys: Leave empty to use default chat command (/ch X).")
        channel_info.setStyleSheet("color: #888888; font-size: 11px;")
        channel_info.setAlignment(Qt.AlignLeft)
        card_layout.addWidget(channel_info)

        # --- AutoLogin Settings ---
        autologin_label = QLabel("AutoLogin Configuration:")
        autologin_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 10px;")
        card_layout.addWidget(autologin_label)

        # Key Sequence
        self.autologin_seq_input = QLineEdit()
        self.autologin_seq_input.setPlaceholderText("Key Sequence e.g. {Enter},{Tab},{F1}")
        self.autologin_seq_input.setStyleSheet("""
            QLineEdit {
                background: #2b2b2b;
                color: white;
                padding: 8px 10px;
                border-radius: 6px;
                border: none;
            }
        """)
        card_layout.addWidget(self.autologin_seq_input)

        # Delays
        delays_layout = QHBoxLayout()
        
        # Start Delay
        self.autologin_delay_input = QLineEdit()
        self.autologin_delay_input.setPlaceholderText("Start Delay (s)")
        self.autologin_delay_input.setText("5")
        self.autologin_delay_input.setStyleSheet("""
            QLineEdit {
                background: #2b2b2b;
                color: white;
                padding: 8px 10px;
                border-radius: 6px;
                border: none;
            }
        """)
        delays_layout.addWidget(QLabel("Start Delay:"))
        delays_layout.addWidget(self.autologin_delay_input)

        # Key Delay
        self.autologin_key_delay_input = QLineEdit()
        self.autologin_key_delay_input.setPlaceholderText("Key Delay (s)")
        self.autologin_key_delay_input.setText("1")
        self.autologin_key_delay_input.setStyleSheet("""
            QLineEdit {
                background: #2b2b2b;
                color: white;
                padding: 8px 10px;
                border-radius: 6px;
                border: none;
            }
        """)
        delays_layout.addWidget(QLabel("Key Delay:"))
        delays_layout.addWidget(self.autologin_key_delay_input)
        
        card_layout.addLayout(delays_layout)

        # AutoLogin info
        autologin_info = QLabel("AutoLogin Key Sequence: Use {Key} for special keys (e.g., {Enter}, {Tab}, {F1}).")
        autologin_info.setStyleSheet("color: #888888; font-size: 11px;")
        autologin_info.setAlignment(Qt.AlignLeft)
        card_layout.addWidget(autologin_info)

        card_layout.addStretch()
        card.setLayout(card_layout)

        page_layout.addWidget(card)
        page_layout.addStretch()

        # Set scroll widget
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def update_channel_inputs(self, count):
        """Rebuild channel input fields based on count."""
        # Save current values
        current_values = {}
        for k, v in self.channel_inputs.items():
            current_values[k] = v.text()
            
        # Clear layout
        while self.channels_layout.count():
            item = self.channels_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.channel_inputs = {}
        
        for i in range(1, count + 1):
            lbl = QLabel(f"Channel {i}:")
            lbl.setStyleSheet("color: #aaaaaa;")
            
            inp = QLineEdit()
            inp.setPlaceholderText(f"e.g. F{i+4}")
            inp.setStyleSheet("""
                QLineEdit {
                    background: #2b2b2b;
                    color: white;
                    padding: 5px 8px;
                    border-radius: 4px;
                    border: none;
                }
                QLineEdit:focus {
                    background: #333333;
                }
            """)
            
            # Restore value if exists
            if str(i) in current_values:
                inp.setText(current_values[str(i)])
                
            self.channel_inputs[str(i)] = inp
            
            row = (i-1) // 2
            col = (i-1) % 2 * 2
            
            self.channels_layout.addWidget(lbl, row, col)
            self.channels_layout.addWidget(inp, row, col + 1)

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
                # combat_page is a QTabWidget, get the first tab (TeleporterTab)
                teleporter_tab = self.main_window.combat_page.widget(0)
                if teleporter_tab and hasattr(teleporter_tab, 'stop_detection'):
                    teleporter_tab.stop_detection()
                    print("Stopped boss farming")
    
    def cleanup(self):
        """Clean up the hotkey listener."""
        self.hotkey_listener.stop()

    def get_settings(self):
        """Return settings for profile saving."""
        channel_hotkeys = {k: v.text() for k, v in self.channel_inputs.items()}
        return {
            "emergency_hotkey": self.hotkey_input.text(),
            "channel_count": self.channel_count_spin.value(),
            "channel_hotkeys": channel_hotkeys,
            "autologin_key_sequence": self.autologin_seq_input.text(),
            "autologin_delay": self.autologin_delay_input.text(),
            "autologin_key_delay": self.autologin_key_delay_input.text()
        }

    def load_settings(self, data):
        """Load settings from profile data."""
        hotkey = data.get("emergency_hotkey", "F9")
        self.hotkey_input.setText(hotkey)
        self.apply_hotkey()
        
        count = data.get("channel_count", 1)
        self.channel_count_spin.setValue(int(count))
        
        channel_hotkeys = data.get("channel_hotkeys", {})
        for k, v in channel_hotkeys.items():
            if k in self.channel_inputs:
                self.channel_inputs[k].setText(v)
                
        self.autologin_seq_input.setText(data.get("autologin_key_sequence", ""))
        self.autologin_delay_input.setText(data.get("autologin_delay", "5"))
        self.autologin_key_delay_input.setText(data.get("autologin_key_delay", "1"))

    def trigger_autologin(self):
        """Trigger the autologin sequence after the specified delay."""
        key_sequence = self.autologin_seq_input.text().strip()
        if not key_sequence:
            return
        
        try:
            delay = int(self.autologin_delay_input.text())
        except ValueError:
            delay = 5
        
        try:
            key_delay = float(self.autologin_key_delay_input.text())
        except ValueError:
            key_delay = 1.0
        
        # Use QTimer to delay the key sending
        QTimer.singleShot(delay * 1000, lambda: self.send_keys(key_sequence, key_delay))
        print(f"AutoLogin: Will send keys '{key_sequence}' in {delay} seconds (key delay: {key_delay}s)")

    def send_keys(self, key_sequence, key_delay=1.0):
        """Send the key sequence to the active window."""
        import time
        import re
        
        # Get the game window handle and activate it
        try:
            from game_context import game_context
            import win32gui
            import win32con
            
            # Retry finding the window a few times
            max_retries = 10
            for attempt in range(max_retries):
                if game_context.hwnd:
                    break
                print(f"AutoLogin: Waiting for game window (attempt {attempt + 1}/{max_retries})...")
                time.sleep(0.5)
                game_context._find_window()
            
            if game_context.hwnd:
                # Bring the game window to the foreground
                win32gui.ShowWindow(game_context.hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(game_context.hwnd)
                time.sleep(0.5)
                print(f"AutoLogin: Game window activated")
            else:
                print(f"AutoLogin: Warning - game window not found after {max_retries} attempts")
                return
        except Exception as e:
            print(f"AutoLogin: Error activating window: {e}")
            return
        
        # Extract all {Key} patterns from the sequence
        key_pattern = re.findall(r'\{([^}]+)\}', key_sequence)
        print(f"AutoLogin: Sending keys: {key_pattern}")
        
        # Import pynput
        from pynput.keyboard import Controller, Key
        keyboard_controller = Controller()
        
        # Key mapping for pynput
        key_map = {
            'F1': Key.f1, 'F2': Key.f2, 'F3': Key.f3, 'F4': Key.f4,
            'F5': Key.f5, 'F6': Key.f6, 'F7': Key.f7, 'F8': Key.f8,
            'F9': Key.f9, 'F10': Key.f10, 'F11': Key.f11, 'F12': Key.f12,
            'Enter': Key.enter, 'Tab': Key.tab, 'Esc': Key.esc, 'Space': Key.space,
            'Up': Key.up, 'Down': Key.down, 'Left': Key.left, 'Right': Key.right,
            'Backspace': Key.backspace, 'Delete': Key.delete,
            'Home': Key.home, 'End': Key.end, 'PageUp': Key.page_up, 'PageDown': Key.page_down,
        }
        
        for key in key_pattern:
            if key:
                try:
                    # Get the pynput key
                    pynput_key = key_map.get(key, None)
                    
                    if pynput_key:
                        print(f"AutoLogin: Pressing key '{key}'")
                        keyboard_controller.press(pynput_key)
                        time.sleep(0.05)
                        keyboard_controller.release(pynput_key)
                    else:
                        # If not in map, try typing it as a character
                        print(f"AutoLogin: Typing character '{key}'")
                        keyboard_controller.type(key)
                    
                    time.sleep(key_delay)
                except Exception as e:
                    print(f"AutoLogin: Error sending key '{key}': {e}")