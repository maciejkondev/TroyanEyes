# gui/pages/main_page.py
from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout

class MainPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.start_button = QPushButton("Start Bot")
        self.status_label = QLabel("Status: Idle")

        layout.addWidget(self.start_button)
        layout.addWidget(self.status_label)

        self.setLayout(layout)
