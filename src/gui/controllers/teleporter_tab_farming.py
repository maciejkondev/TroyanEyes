"""
Boss farming manager skeleton.
Legacy logic removed.
"""

from typing import Optional, Any
from PySide6.QtCore import QObject

class BossFarmingConfig:
    """Configuration manager skeleton."""
    
    def __init__(self):
        self.config = {"boss": {}, "metin": {}}

    def get_boss_config(self):
        return self.config["boss"]

    def get_metin_config(self):
        return self.config["metin"]
        
    def update_boss_config(self, updates):
        pass

class BossFarmingManager(QObject):
    """Manager skeleton."""

    def __init__(self):
        super().__init__()
        self.config_manager = BossFarmingConfig()
        self.boss_worker = None
        self.hotkey_listener = None
        # Template persistence is now handled by worker (Issue 8)

    def start_boss_farming(self, priority_list=None, click_enabled=True, num_channels=1, ocr_backend="CPU", pelerynka_key="F1", show_preview=True, channel_hotkeys=None, ignore_stuck=True, stuck_timeout=30) -> Optional[Any]:
        from gui.controllers.teleporter_tab_worker import BossDetectionWorker
        config = {}
        if priority_list:
            config["map_priority"] = priority_list
        config["click_enabled"] = click_enabled
        config["num_channels"] = num_channels
        config["ocr_backend"] = ocr_backend
        config["pelerynka_key"] = pelerynka_key
        config["show_preview"] = show_preview
        config["channel_hotkeys"] = channel_hotkeys or {}
        config["ignore_stuck"] = ignore_stuck
        config["stuck_timeout"] = stuck_timeout
        # Note: Worker handles template loading from disk automatically
            
        self.boss_worker = BossDetectionWorker(config)
        self.boss_worker.start()
        return self.boss_worker

    def stop_boss_farming(self):
        if self.boss_worker:
            # Worker handles template persistence internally now
            self.boss_worker.stop()
            self.boss_worker = None

    def pause_boss_farming(self):
        if self.boss_worker:
            self.boss_worker.pause()

    def resume_boss_farming(self):
        if self.boss_worker:
            self.boss_worker.resume()

    def reset_boss_farming(self):
        if self.boss_worker:
            self.boss_worker.reset()

    def switch_to_channel(self, channel_index: int):
        pass

    def get_config_manager(self):
        return self.config_manager
        
    def cleanup(self):
        self.stop_boss_farming()