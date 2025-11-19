"""
Boss detection worker skeleton.
Legacy OpenCV logic removed.
"""

from PySide6.QtCore import QThread, Signal
import time

class BossDetectionWorker(QThread):
    """
    Worker thread skeleton.
    """

    frame_captured = Signal(object) # Changed to object to avoid numpy dependency for now
    status_changed = Signal(str)
    target_found = Signal()
    target_lost = Signal()
    detection_triggered = Signal(dict)
    stats_updated = Signal(dict)
    channel_switched = Signal(int)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.running = False
        self.paused = False
        self.should_stop = False
        self.last_switch_time = 0.0 # Keep for compatibility if needed

    def run(self):
        """Main loop skeleton."""
        self.running = True
        self.status_changed.emit("Worker started (Logic removed)")
        
        while not self.should_stop:
            time.sleep(1)
            
        self.running = False
        self.status_changed.emit("Worker stopped")

    def stop(self):
        self.should_stop = True
        self.wait()

    def pause(self):
        self.paused = True
        self.status_changed.emit("Paused")

    def resume(self):
        self.paused = False
        self.status_changed.emit("Resumed")

    def reset(self):
        self.status_changed.emit("Reset")

    def _switch_to_channel(self, channel_index: int, hotkey_config: dict = None):
        pass

