# src/troyaneyes/services/templates/teleporter_templates.py
from __future__ import annotations

import pickle
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

Rect = Tuple[int, int, int, int]

BOSS_TEMPLATE_KEY = "__boss_indicator__"


@dataclass
class TeleporterTemplate:
    name: str
    rect: Rect
    image_size: Tuple[int, int]
    process_name: str
    snapshot: Optional[np.ndarray] = None


class TeleporterTemplateRepository:
    """
    Templates remain here.

    UI state (map order) is NOT stored here (stored in profile.json).
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        if base_dir is None:
            base_dir = Path.cwd() / "temp_dir"

        base_dir.mkdir(parents=True, exist_ok=True)
        self._path = base_dir / "teleporter_templates.pkl"
        self._lock = threading.Lock()

    # ---------------------------------------------------------

    def load_all(self) -> Dict[str, TeleporterTemplate]:
        if not self._path.exists():
            return {}
        with self._lock, self._path.open("rb") as f:
            data = pickle.load(f)
        return data if isinstance(data, dict) else {}

    # ---------------------------------------------------------

    def save_all(self, templates: Dict[str, TeleporterTemplate]) -> None:
        with self._lock, self._path.open("wb") as f:
            pickle.dump(templates, f)

    # ---------------------------------------------------------

    def save_template(self, template: TeleporterTemplate) -> None:
        templates = self.load_all()
        templates[template.name] = template
        self.save_all(templates)

    def get_template(self, name: str) -> Optional[TeleporterTemplate]:
        return self.load_all().get(name)
