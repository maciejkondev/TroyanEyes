# src/main.py

import sys
import os

# Suppress Qt DPI awareness warning/error
# os.environ["QT_QPA_PLATFORM"] = "windows:dpiawareness=1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure PyInstaller can find modules if the app is bundled as an executable
if getattr(sys, 'frozen', False):
    # Add bundled paths to sys.path
    base_path = sys._MEIPASS
    sys.path.append(base_path)

def main():
    app = QApplication(sys.argv)
    
    # Import MainWindow AFTER QApplication to avoid DPI context conflicts (e.g. with OpenCV)
    from gui.windows.main_window import MainWindow
    
    # Create and show the MainWindow
    window = MainWindow()
    window.show()

    # Execute the application's event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()