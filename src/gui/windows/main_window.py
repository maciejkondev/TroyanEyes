import os
import sys
import subprocess
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QToolBar,
    QStackedWidget,
    QFrame,
    QComboBox,
    QInputDialog
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QTimer
from utils.profile_manager import ProfileManager


# --------------------------
# Modern Container Widget
# --------------------------
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


# --------------------------
# Start Page
# --------------------------
class MainPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.profile_manager = ProfileManager()
        self.process = None
        self.initUI()

    def initUI(self):

        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(40, 10, 40, 30)
        page_layout.setSpacing(25)

        card = Card()
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # --- Profile Section ---
        profile_layout = QHBoxLayout()
        
        self.profile_label = QLabel("Profile")
        self.profile_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        
        self.profile_combo = QComboBox()
        self.profile_combo.setStyleSheet("""
            QComboBox {
                background: #2b2b2b;
                color: white;
                padding: 5px;
                border: 1px solid #444;
                border-radius: 4px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.profile_combo.currentIndexChanged.connect(self.on_profile_changed)

        self.btn_new_profile = QPushButton("+")
        self.btn_new_profile.setToolTip("Create New Profile")
        self.btn_new_profile.setFixedSize(30, 30)
        self.btn_new_profile.clicked.connect(self.create_profile)
        
        self.btn_save_profile = QPushButton("💾")
        self.btn_save_profile.setToolTip("Save Current Profile")
        self.btn_save_profile.setFixedSize(30, 30)
        self.btn_save_profile.clicked.connect(self.save_current_profile)

        self.btn_del_profile = QPushButton("🗑️")
        self.btn_del_profile.setToolTip("Delete Current Profile")
        self.btn_del_profile.setFixedSize(30, 30)
        self.btn_del_profile.clicked.connect(self.delete_current_profile)

        button_style_small = """
            QPushButton {
                background: #3a3a3a;
                color: white;
                border-radius: 4px;
                border: 1px solid #555;
            }
            QPushButton:hover { background: #474747; }
            QPushButton:pressed { background: #323232; }
        """
        self.btn_new_profile.setStyleSheet(button_style_small)
        self.btn_save_profile.setStyleSheet(button_style_small)
        self.btn_del_profile.setStyleSheet(button_style_small)

        profile_layout.addWidget(self.profile_label)
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addWidget(self.btn_new_profile)
        profile_layout.addWidget(self.btn_save_profile)
        profile_layout.addWidget(self.btn_del_profile)
        profile_layout.addStretch()

        # --- Label Row ---
        label_row = QHBoxLayout()

        self.path_label = QLabel("Executable Path")
        self.path_label.setStyleSheet("color: #cccccc; font-size: 14px;")

        label_row.addWidget(self.path_label)
        label_row.addStretch()

        # --- Input and buttons ---
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Choose an .exe file...")
        self.path_input.setStyleSheet("""
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

        self.browse_button = QPushButton("Browse")
        self.run_button = QPushButton("Run")

        button_style = """
            QPushButton {
                background: #3a3a3a;
                color: white;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #555;
            }
            QPushButton:hover { background: #474747; }
            QPushButton:pressed { background: #323232; }
            QPushButton:disabled {
                background: #2a2a2a;
                color: #888;
            }
        """
        self.browse_button.setStyleSheet(button_style)
        self.run_button.setStyleSheet(button_style)

        self.browse_button.clicked.connect(self.open_file_dialog)
        self.run_button.clicked.connect(self.run_exe)

        # --- Info text under RUN ---
        info_label = QLabel(
            "Note: This program does not require administrator privileges\n"
            "unless the Metin2 client itself requires them."
        )
        info_label.setStyleSheet("color: #888888; font-size: 11px;")
        info_label.setAlignment(Qt.AlignCenter)

        # --- Add widgets to card ---
        card_layout.addLayout(profile_layout)
        card_layout.addSpacing(10)
        card_layout.addLayout(label_row)
        card_layout.addWidget(self.path_input)
        card_layout.addWidget(self.browse_button)
        card_layout.addWidget(self.run_button)
        card_layout.addSpacing(10)
        card_layout.addWidget(info_label)   # <--- HERE
        card_layout.addSpacing(5)

        card.setLayout(card_layout)

        page_layout.addWidget(card)
        page_layout.addStretch()

        self.setLayout(page_layout)
        self.setStyleSheet("background-color: #151515;")

        # Don't load profiles here - will be done after MainWindow is fully initialized

    def load_profiles_to_ui(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        names = self.profile_manager.get_profile_names()
        self.profile_combo.addItems(names)
        
        if self.profile_manager.last_used and self.profile_manager.last_used in names:
            self.profile_combo.setCurrentText(self.profile_manager.last_used)
        elif names:
            self.profile_combo.setCurrentIndex(0)
            
        self.profile_combo.blockSignals(False)
        self.on_profile_changed()

    def on_profile_changed(self):
        name = self.profile_combo.currentText()
        if not name:
            self.path_input.clear()
            return
            
        self.profile_manager.set_last_used(name)
        data = self.profile_manager.get_profile(name)
        self.path_input.setText(data.get("exe_path", ""))
        
        # Load settings into other pages
        if self.main_window and hasattr(self.main_window, 'combat_page'):
            self.main_window.combat_page.load_settings(data)
        if self.main_window and hasattr(self.main_window, 'autologin_page'):
            self.main_window.autologin_page.load_settings(data)

    def create_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile Name:")
        if ok and name:
            if name in self.profile_manager.get_profile_names():
                QMessageBox.warning(self, "Error", "Profile already exists!")
                return
            
            # Save current input as the new profile data
            data = {"exe_path": self.path_input.text()}
            
            # Include settings from other pages
            if self.main_window and hasattr(self.main_window, 'combat_page'):
                data.update(self.main_window.combat_page.get_settings())
            if self.main_window and hasattr(self.main_window, 'autologin_page'):
                data.update(self.main_window.autologin_page.get_settings())
                
            self.profile_manager.save_profile(name, data)
            self.load_profiles_to_ui()
            self.profile_combo.setCurrentText(name)

    def save_current_profile(self):
        name = self.profile_combo.currentText()
        if not name:
            QMessageBox.warning(self, "Error", "No profile selected!")
            return
            
        data = {"exe_path": self.path_input.text()}
        
        # Include settings from other pages
        if self.main_window and hasattr(self.main_window, 'combat_page'):
            data.update(self.main_window.combat_page.get_settings())
        if self.main_window and hasattr(self.main_window, 'autologin_page'):
            data.update(self.main_window.autologin_page.get_settings())
            
        self.profile_manager.save_profile(name, data)
        QMessageBox.information(self, "Success", f"Profile '{name}' saved!")

    def delete_current_profile(self):
        name = self.profile_combo.currentText()
        if not name:
            return
            
        reply = QMessageBox.question(self, "Delete Profile", 
                                   f"Are you sure you want to delete profile '{name}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.profile_manager.delete_profile(name)
            self.load_profiles_to_ui()

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select .exe file",
            "",
            "Executable Files (*.exe);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def run_exe(self):
        path = self.path_input.text()

        if not os.path.isfile(path):
            QMessageBox.warning(self, "Invalid Path", "Please select a valid .exe file.")
            return

        try:
            self.process = subprocess.Popen(path, cwd=os.path.dirname(path))
            
            # Register the process with GameContext
            from game_context import game_context
            game_context.set_process(self.process.pid)
            
            print(f"Launched: {path} (PID: {self.process.pid})")
            
            # Trigger autologin if configured
            if self.main_window and hasattr(self.main_window, 'autologin_page'):
                self.main_window.autologin_page.trigger_autologin()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not run file:\n{e}")

    def cleanup(self):
        """Terminates the attached process if it exists."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None


# --------------------------
# AutoLogin Page
# --------------------------
class AutoLoginPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.initUI()

    def initUI(self):
        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(40, 10, 40, 30)
        page_layout.setSpacing(25)

        card = Card()
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # --- Title ---
        title = QLabel("AutoLogin Configuration")
        title.setStyleSheet("color: #cccccc; font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title)

        # --- Key Sequence Input ---
        key_label = QLabel("Key Sequence (comma-separated):")
        key_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        card_layout.addWidget(key_label)

        self.key_sequence_input = QLineEdit()
        self.key_sequence_input.setPlaceholderText("e.g. {Enter},{Tab},{F1}")
        self.key_sequence_input.setStyleSheet("""
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
        card_layout.addWidget(self.key_sequence_input)

        # --- Delay Input ---
        delay_label = QLabel("Delay before sending (seconds):")
        delay_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        card_layout.addWidget(delay_label)

        self.delay_input = QLineEdit()
        self.delay_input.setText("5")
        self.delay_input.setPlaceholderText("5")
        self.delay_input.setStyleSheet("""
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
        card_layout.addWidget(self.delay_input)

        # --- Key Delay Input ---
        key_delay_label = QLabel("Delay between keys (seconds):")
        key_delay_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        card_layout.addWidget(key_delay_label)

        self.key_delay_input = QLineEdit()
        self.key_delay_input.setText("1")
        self.key_delay_input.setPlaceholderText("1")
        self.key_delay_input.setStyleSheet("""
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
        card_layout.addWidget(self.key_delay_input)

        # --- Info ---
        info_label = QLabel(
            "Keys will be sent to the game window after the specified delay.\n"
            "Format: {Key},{Key},...\n"
            "Examples: {Enter}, {Tab}, {Esc}, {F1}, {Space}, etc."
        )
        info_label.setStyleSheet("color: #888888; font-size: 11px;")
        info_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(info_label)

        card_layout.addStretch()
        card.setLayout(card_layout)

        page_layout.addWidget(card)
        page_layout.addStretch()

        self.setLayout(page_layout)
        self.setStyleSheet("background-color: #151515;")

    def get_settings(self):
        """Return current autologin settings for profile saving."""
        return {
            "autologin_key_sequence": self.key_sequence_input.text(),
            "autologin_delay": self.delay_input.text(),
            "autologin_key_delay": self.key_delay_input.text()
        }

    def load_settings(self, data):
        """Load autologin settings from profile data."""
        self.key_sequence_input.setText(data.get("autologin_key_sequence", ""))
        self.delay_input.setText(data.get("autologin_delay", "5"))
        self.key_delay_input.setText(data.get("autologin_key_delay", "1"))

    def trigger_autologin(self):
        """Trigger the autologin sequence after the specified delay."""
        key_sequence = self.key_sequence_input.text().strip()
        if not key_sequence:
            return
        
        try:
            delay = int(self.delay_input.text())
        except ValueError:
            delay = 5
        
        try:
            key_delay = float(self.key_delay_input.text())
        except ValueError:
            key_delay = 1.0
        
        # Use QTimer to delay the key sending
        QTimer.singleShot(delay * 1000, lambda: self.send_keys(key_sequence, key_delay))
        print(f"AutoLogin: Will send keys '{key_sequence}' in {delay} seconds (key delay: {key_delay}s)")

    def send_keys(self, key_sequence, key_delay=1.0):
        """Send the key sequence to the active window."""
        import pyautogui
        import time
        import re
        
        # Get the game window handle and activate it
        try:
            from game_context import game_context
            import win32gui
            import win32con
            
            # Retry finding the window a few times (it may take time to appear)
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
                time.sleep(0.5)  # Give it time to activate
                print(f"AutoLogin: Game window activated")
            else:
                print(f"AutoLogin: Warning - game window not found after {max_retries} attempts")
                return  # Don't send keys if window not found
        except Exception as e:
            print(f"AutoLogin: Error activating window: {e}")
            return
        
        # Extract all {Key} patterns from the sequence
        key_pattern = re.findall(r'\{([^}]+)\}', key_sequence)
        print(f"AutoLogin: Sending keys: {key_pattern}")
        
        # Import pynput
        from pynput.keyboard import Controller, Key
        keyboard = Controller()
        
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
                        keyboard.press(pynput_key)
                        time.sleep(0.05)
                        keyboard.release(pynput_key)
                    else:
                        # If not in map, try typing it as a character
                        print(f"AutoLogin: Typing character '{key}'")
                        keyboard.type(key)
                    
                    time.sleep(key_delay)  # Configurable delay between keys
                except Exception as e:
                    print(f"AutoLogin: Error sending key '{key}': {e}")


# --------------------------
# Placeholder Pages (NO TITLES)
# --------------------------
class SimplePage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 10, 40, 30)
        layout.addStretch()

        self.setLayout(layout)
        self.setStyleSheet("background-color: #151515;")


# --------------------------
# Main Window
# --------------------------
from gui.pages.combat_page import combat_page
from gui.pages.settings_page import SettingsPage

# --------------------------
# Main Window
# --------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("TroyanEyes by maciejkondev")
        self.setMinimumSize(600, 400)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.start_page = MainPage(main_window=self)
        self.combat_page = combat_page()
        self.exp_page = SimplePage()
        self.autologin_page = AutoLoginPage(main_window=self)
        self.settings_page = SettingsPage(main_window=self)

        self.stack.addWidget(self.start_page)
        self.stack.addWidget(self.combat_page)
        self.stack.addWidget(self.exp_page)
        self.stack.addWidget(self.autologin_page)
        self.stack.addWidget(self.settings_page)

        self.menuBar().hide()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.setup_toolbar()
        
        # Load profiles after all pages are initialized
        self.start_page.load_profiles_to_ui()

    def setup_toolbar(self):
        self.toolbar = QToolBar()
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.toolbar.setStyleSheet("""
            QToolBar {
                background: #1c1c1c;
                spacing: 10px;
                padding: 4px;
            }
            QToolButton {
                background: none;
                padding: 6px 12px;
                border-radius: 6px;
                color: white;
            }
            QToolButton:hover {
                background-color: #333;
            }
            QToolButton:checked {
                background-color: #4CAF50;
                color: black;
            }
        """)

        self.buttons = []

        def add_button(icon, label, index):
            action = QAction(icon, label, self)
            action.setCheckable(True)
            self.toolbar.addAction(action)
            action.triggered.connect(lambda: self.switch_page(index))
            self.buttons.append(action)
            return action

        self.btn_start = add_button(QIcon(), "Start", 0)
        self.btn_bossing = add_button(QIcon(), "Combat", 1)
        self.btn_exp = add_button(QIcon(), "AutoEXP", 2)
        self.btn_autologin = add_button(QIcon(), "AutoLogin", 3)
        self.btn_settings = add_button(QIcon(), "Settings", 4)

        self.btn_start.setChecked(True)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.status_label.setText(f"Current Page: {self.buttons[index].text()}")

    def closeEvent(self, event):
        """Handle application closure."""
        self.start_page.cleanup()
        if hasattr(self.settings_page, 'cleanup'):
            self.settings_page.cleanup()
        event.accept()
