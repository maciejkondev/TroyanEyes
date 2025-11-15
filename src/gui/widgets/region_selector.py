"""
Full-screen translucent region selector.
Emits a QRect in global screen coordinates when user selects a rectangle.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPen, QColor


class RegionSelector(QWidget):
    """Full-screen translucent overlay for selecting a screen region.

    Signals:
        region_selected(QRect) -- emits selected rect in global screen coordinates
        cancelled() -- emitted when selection was cancelled (ESC)
    """

    region_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)

        self.start_pos = None
        self.current_rect = QRect()
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        # dim entire background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        if not self.current_rect.isNull():
            pen = QPen(QColor(0, 180, 255), 2)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 180, 255, 50))
            painter.drawRect(self.current_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.globalPosition().toPoint()
            self.current_rect = QRect(self.start_pos, self.start_pos)
            self.update()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            p = event.globalPosition().toPoint()
            self.current_rect = QRect(self.start_pos, p).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self.current_rect.isNull():
            rect = self.current_rect
            # reset visual state before emitting
            self.start_pos = None
            self.current_rect = QRect()
            self.hide()
            self.region_selected.emit(rect)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.cancelled.emit()
