# src/main.py

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure PyInstaller can find modules if the app is bundled as an executable
if getattr(sys, 'frozen', False):
    # Add bundled paths to sys.path
    base_path = sys._MEIPASS
    sys.path.append(base_path)

# Import the MainWindow class from main_window.py
from gui.windows.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    
    # Create and show the MainWindow
    window = MainWindow()
    window.show()

    # Execute the application's event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()