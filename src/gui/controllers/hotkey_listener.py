"""
Global hotkey listener for bot automation control.
Allows starting/stopping/pausing farming via keyboard shortcuts even when app is not focused.
"""

from PySide6.QtCore import QThread, Signal
from pynput import keyboard
import time


class HotkeyListener(QThread):
    """
    Thread for listening to global keyboard hotkeys.
    
    Signals:
    - hotkey_triggered: emitted with action name ("start", "stop", "pause", "reset")
    - channel_hotkey_triggered: emitted with channel index when a channel hotkey is pressed
    """

    hotkey_triggered = Signal(str)  # Action name
    channel_hotkey_triggered = Signal(int)  # Channel index (1-12)
    status_changed = Signal(str)    # Status message

    # Mapping of key names to pynput key objects
    KEY_MAP = {
        "F1": keyboard.Key.f1,
        "F2": keyboard.Key.f2,
        "F3": keyboard.Key.f3,
        "F4": keyboard.Key.f4,
        "F5": keyboard.Key.f5,
        "F6": keyboard.Key.f6,
        "F7": keyboard.Key.f7,
        "F8": keyboard.Key.f8,
        "F9": keyboard.Key.f9,
        "F10": keyboard.Key.f10,
        "F11": keyboard.Key.f11,
        "F12": keyboard.Key.f12,
    }
    
    MODIFIER_MAP = {
        'shift': keyboard.Key.shift,
        'ctrl': keyboard.Key.ctrl,
        'alt': keyboard.Key.alt,
    }

    def __init__(self, config: dict):
        """
        Initialize hotkey listener.
        
        Args:
            config (dict): Configuration containing:
                - enabled: bool
                - start: str (key name, e.g., "F1")
                - stop: str (key name, e.g., "F2")
                - pause: str (key name, e.g., "F3")
                - reset: str (key name, e.g., "F4")
                - channel_hotkeys: list of dicts with 'channel', 'key', and 'modifier'
        """
        super().__init__()
        self.config = config
        self.running = False
        self.should_stop = False
        self.listener = None
        self.pressed_keys = set()  # Track currently pressed keys

    def run(self):
        """Main thread loop for listening to hotkeys."""
        if not self.config.get("enabled", False):
            self.status_changed.emit("Hotkeys disabled")
            return

        try:
            self.running = True
            self._setup_hotkeys()
            self.status_changed.emit("Hotkey listener started")

            # Keep thread alive
            while not self.should_stop:
                time.sleep(0.1)

        except Exception as e:
            self.status_changed.emit(f"Hotkey listener error: {str(e)}")
        finally:
            self.running = False

    def _setup_hotkeys(self):
        """Set up the hotkey listener with configured keys."""
        hotkey_config = {
            "start": self.config.get("start", "F1"),
            "stop": self.config.get("stop", "F2"),
            "pause": self.config.get("pause", "F3"),
            "reset": self.config.get("reset", "F4"),
        }
        
        # Channel hotkeys: list of {'channel': 1, 'key': 'F1', 'modifier': 'shift'}
        channel_hotkeys = self.config.get("channel_hotkeys", [])

        def on_press(key):
            """Callback when a key is pressed."""
            try:
                self.pressed_keys.add(key)
                
                # Check each configured farming hotkey
                for action, key_name in hotkey_config.items():
                    if key_name in self.KEY_MAP:
                        if key == self.KEY_MAP[key_name]:
                            self.hotkey_triggered.emit(action)
                            break
                
                # Check channel hotkeys with modifiers
                for ch_config in channel_hotkeys:
                    key_name = ch_config.get('key')
                    modifier = ch_config.get('modifier')
                    channel = ch_config.get('channel')
                    
                    if key_name not in self.KEY_MAP:
                        continue
                    
                    # Check if key matches
                    if key == self.KEY_MAP[key_name]:
                        # Check modifier if specified
                        if modifier and modifier.lower() in self.MODIFIER_MAP:
                            mod_key = self.MODIFIER_MAP[modifier.lower()]
                            if mod_key in self.pressed_keys:
                                self.channel_hotkey_triggered.emit(channel)
                                break
                        elif not modifier:
                            # No modifier required
                            self.channel_hotkey_triggered.emit(channel)
                            break
            except AttributeError:
                # key doesn't have the attributes we need
                pass
            except Exception as e:
                self.status_changed.emit(f"Hotkey error: {str(e)}")

        def on_release(key):
            """Callback when a key is released."""
            try:
                self.pressed_keys.discard(key)
            except Exception:
                pass

        # Create listener
        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()

    def stop(self):
        """Stop the hotkey listener."""
        self.should_stop = True
        if self.listener:
            self.listener.stop()
        self.wait()

    @staticmethod
    def get_available_keys():
        """Get list of available key options for UI."""
        return list(HotkeyListener.KEY_MAP.keys())
