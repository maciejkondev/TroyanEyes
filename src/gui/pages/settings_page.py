from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SettingsPage(QWidget):
    """Empty settings page – ready for future configuration UI."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Create a minimal UI with just a title."""
        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        # Placeholder for future settings widgets
        self.setLayout(layout)