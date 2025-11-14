from PySide6.QtWidgets import QApplication
from gui.windows.main_window import MainWindow
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())
