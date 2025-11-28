from PySide6.QtCore import QObject, Signal
from gui.controllers.boss_tab_worker import BossTabWorker

class BossTabManager(QObject):
    frame_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        self.worker = None

    def start_detection(self):
        if self.worker is not None and self.worker.isRunning():
            return

        self.worker = BossTabWorker()
        self.worker.frame_processed.connect(self.handle_frame)
        self.worker.status_update.connect(self.handle_status)
        self.worker.start()

    def stop_detection(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    def handle_frame(self, frame):
        self.frame_update.emit(frame)

    def handle_status(self, status):
        self.status_update.emit(status)
