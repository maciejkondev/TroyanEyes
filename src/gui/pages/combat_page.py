"""
Combat page with empty tabs for Boss and Metin farming.
This file provides placeholder UI components after cleanup.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton
from PySide6.QtCore import Qt
from gui.controllers.boss_farming import BossFarmingManager

class CombatPage(QWidget):
    """Main combat farming page with empty tabs."""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Combat Farming")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(BossFarmingTab(), "Boss Farming")
        tabs.addTab(MetinFarmingTab(), "Metin Farming")
        layout.addWidget(tabs)
        self.setLayout(layout)

class BossFarmingTab(QWidget):
    """Tab for boss farming with YOLO detection control."""
    def __init__(self):
        super().__init__()
        self.manager = BossFarmingManager()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.toggle_btn = QPushButton("Start Detection")
        self.toggle_btn.clicked.connect(self.toggle_farming)
        layout.addWidget(self.toggle_btn)
        
        layout.addStretch()
        self.setLayout(layout)

    def toggle_farming(self):
        if self.toggle_btn.text() == "Start Detection":
            self.manager.start_boss_farming()
            self.toggle_btn.setText("Stop Detection")
            self.status_label.setText("Status: Running")
        else:
            self.manager.stop_boss_farming()
            self.toggle_btn.setText("Start Detection")
            self.status_label.setText("Status: Stopped")

class MetinFarmingTab(QWidget):
    """Placeholder tab for metin farming UI."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        placeholder = QLabel("Metin Farming UI will be added here.")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder)
        self.setLayout(layout)
