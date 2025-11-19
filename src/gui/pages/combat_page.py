"""
Combat page with empty tabs for Boss and Metin farming.
This file provides placeholder UI components after cleanup.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from PySide6.QtCore import Qt

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
    """Placeholder tab for boss farming UI."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        placeholder = QLabel("Boss Farming UI will be added here.")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder)
        self.setLayout(layout)

class MetinFarmingTab(QWidget):
    """Placeholder tab for metin farming UI."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        placeholder = QLabel("Metin Farming UI will be added here.")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder)
        self.setLayout(layout)
