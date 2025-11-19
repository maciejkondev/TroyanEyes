# main.py  (root launcher for PyInstaller)

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure PyInstaller can find modules
if getattr(sys, 'frozen', False):  # Running as EXE
    # Add bundled paths
    base_path = sys._MEIPASS
    sys.path.append(base_path)

# Import MainWindow
from gui.windows.main_window import MainWindow


def main():


    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
