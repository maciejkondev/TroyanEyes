# src/troyaneyes/services/profile_store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

class ProfileStore:
    """
    Stores persistent UI/user data such as:
        - map_order: list[str]

    File location:
        ./temp_dir/profile.json
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path.cwd() / "temp_dir"
        base_dir.mkdir(parents=True, exist_ok=True)

        self._path = base_dir / "profile.json"

    # ---------------------------------------------------------

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    # ---------------------------------------------------------

    def save(self, data: Dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self._path)

    # ---------------------------------------------------------

    def load_map_order(self) -> List[str]:
        data = self.load()
        return data.get("map_order", [])

    def save_map_order(self, order: List[str]) -> None:
        data = self.load()
        data["map_order"] = order
        self.save(data)
