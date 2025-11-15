"""
Boss farming manager to orchestrate detection workers and farming logic.
"""

import json
import os
from typing import Optional, Dict, Any


class BossFarmingConfig:
    """Configuration manager for boss farming settings."""

    DEFAULT_CONFIG = {
        "boss": {
            "enabled": True,
            "region": (250, 120, 260, 215),  # (left, top, width, height)
            "template_path": "assets/templates/dostepny_template.png",
            "match_threshold": 0.8,
            "click_offset_x": 20,
            "loop_delay": 0.1,
            "num_channels": 6,
            "channel_switch_interval": 2.0,
            "start_channel": 1,
            "lock_timeout": 10.0,
            "unavailable_timeout": 10.0,  # seconds before marking a boss unkillable
            "swap_interval": 300,  # 5 minutes
            "swap_x_offset": -100,
            "swap_y_offsets": [0, 50, 100],
            "hotkeys": {
                "enabled": False,
                "start": "F9",
                "stop": "F10",
                "pause": "F11",
                "reset": "F12",
            },
        },
        "metin": {
            "enabled": False,  # Placeholder for future Metin farming
            "region": (250, 120, 260, 215),
            "template_path": "assets/templates/metin_template.png",
            "match_threshold": 0.8,
            "click_offset_x": 20,
            "loop_delay": 0.1,
            "hotkeys": {
                "enabled": False,
                "start": "F5",
                "stop": "F6",
                "pause": "F7",
                "reset": "F8",
            },
        },
    }

    def __init__(self, config_path: str = "assets/config/boss_farming.json"):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to JSON configuration file
        """
        self.config_path = config_path
        self.config = self._load_or_create_config()

    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load config from file or create default if missing."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config from {self.config_path}: {e}")
                print("Using default configuration")

        # Create default config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self._save_config(self.DEFAULT_CONFIG)
        return self.DEFAULT_CONFIG.copy()

    def _save_config(self, config: Dict[str, Any]):
        """Save config to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config to {self.config_path}: {e}")

    def get_boss_config(self) -> Dict[str, Any]:
        """Get boss farming configuration."""
        return self.config.get("boss", self.DEFAULT_CONFIG["boss"].copy())

    def get_metin_config(self) -> Dict[str, Any]:
        """Get metin farming configuration."""
        return self.config.get("metin", self.DEFAULT_CONFIG["metin"].copy())

    def update_boss_config(self, updates: Dict[str, Any]):
        """Update boss configuration."""
        if "boss" not in self.config:
            self.config["boss"] = self.DEFAULT_CONFIG["boss"].copy()
        self.config["boss"].update(updates)
        self._save_config(self.config)

    def update_metin_config(self, updates: Dict[str, Any]):
        """Update metin configuration."""
        if "metin" not in self.config:
            self.config["metin"] = self.DEFAULT_CONFIG["metin"].copy()
        self.config["metin"].update(updates)
        self._save_config(self.config)

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save_config(self.config)


class BossFarmingManager:
    """Manages boss farming workers and coordinates farming operations."""

    def __init__(self, config_path: str = "assets/config/boss_farming.json"):
        """
        Initialize farming manager.
        
        Args:
            config_path: Path to JSON configuration file
        """
        self.config_manager = BossFarmingConfig(config_path)
        self.boss_worker = None
        self.metin_worker = None
        self.hotkey_listener = None

    def start_boss_farming(self) -> Optional[Any]:
        """
        Start boss farming worker.
        
        Returns:
            BossDetectionWorker instance or None if error
        """
        try:
            from gui.controllers.boss_worker import BossDetectionWorker

            config = self.config_manager.get_boss_config()
            self.boss_worker = BossDetectionWorker(config)
            self.boss_worker.start()
            return self.boss_worker
        except Exception as e:
            print(f"Error starting boss farming: {e}")
            return None

    def stop_boss_farming(self):
        """Stop boss farming worker."""
        if self.boss_worker:
            self.boss_worker.stop()
            self.boss_worker = None

    def pause_boss_farming(self):
        """Pause boss farming (keep thread running)."""
        if self.boss_worker and self.boss_worker.running:
            self.boss_worker.pause()

    def resume_boss_farming(self):
        """Resume boss farming."""
        if self.boss_worker and self.boss_worker.running:
            self.boss_worker.resume()

    def reset_boss_farming(self):
        """Reset boss farming state."""
        if self.boss_worker and self.boss_worker.running:
            self.boss_worker.reset()

    def switch_to_channel(self, channel_index: int):
        """Switch to a specific channel (called from hotkey listener).
        
        Respects the channel_switch_interval timeout to prevent too-frequent switches.
        """
        if not self.boss_worker or not self.boss_worker.running:
            return
        
        # Check if enough time has passed since last switch
        import time
        from datetime import datetime
        now = time.time()
        config = self.config_manager.get_boss_config()
        interval = config.get("channel_switch_interval", 2.0)
        
        if now - self.boss_worker.last_switch_time < interval:
            # Not enough time has passed, skip this switch
            remaining = interval - (now - self.boss_worker.last_switch_time)
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.boss_worker.status_changed.emit(
                f"[{timestamp}] Channel switch on cooldown ({remaining:.1f}s remaining)"
            )
            return
        
        channel_hotkeys = config.get("channel_hotkeys", [])
        
        # Find the hotkey config for this channel
        hotkey_config = None
        for ch_config in channel_hotkeys:
            if ch_config.get('channel') == channel_index:
                hotkey_config = ch_config
                break
        
        # Switch channel (pass hotkey config to use that instead of default)
        self.boss_worker._switch_to_channel(channel_index, hotkey_config)

    def start_metin_farming(self) -> Optional[Any]:
        """Start metin farming worker (placeholder for future implementation)."""
        print("Metin farming not yet implemented")
        return None

    def stop_metin_farming(self):
        """Stop metin farming worker."""
        if self.metin_worker:
            self.metin_worker.stop()
            self.metin_worker = None

    def get_config_manager(self) -> BossFarmingConfig:
        """Get configuration manager instance."""
        return self.config_manager

    def cleanup(self):
        """Clean up workers."""
        self.stop_boss_farming()
        self.stop_metin_farming()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
