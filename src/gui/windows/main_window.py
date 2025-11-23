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
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt


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
        self.initUI()

    def initUI(self):

        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(40, 10, 40, 30)
        page_layout.setSpacing(25)

        card = Card()
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # --- Label Row ---
        label_row = QHBoxLayout()

        self.path_label = QLabel("Executable Path:")
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
            subprocess.Popen(path, cwd=os.path.dirname(path))
            QMessageBox.information(self, "Success", f"Launched:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not run file:\n{e}")


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
from gui.pages.combat_page import CombatPage

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
        self.bossing_page = CombatPage()
        self.exp_page = SimplePage()
        self.autologin_page = SimplePage()
        self.settings_page = SimplePage()

        self.stack.addWidget(self.start_page)
        self.stack.addWidget(self.bossing_page)
        self.stack.addWidget(self.exp_page)
        self.stack.addWidget(self.autologin_page)
        self.stack.addWidget(self.settings_page)

        self.menuBar().hide()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.setup_toolbar()

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
        self.btn_bossing = add_button(QIcon(), "Bossing", 1)
        self.btn_exp = add_button(QIcon(), "AutoEXP", 2)
        self.btn_autologin = add_button(QIcon(), "AutoLogin", 3)
        self.btn_settings = add_button(QIcon(), "Settings", 4)

        self.btn_start.setChecked(True)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.status_label.setText(f"Current Page: {self.buttons[index].text()}")
