import os
import shutil
import sys
import tempfile
from pathlib import Path


TEMP_FOLDER_NAME = "TroyanEyes"


def initialize_temp_dir() -> Path:
    """Create and return a stable temp directory for the application.

    On Windows, prefer ``%LOCALAPPDATA%\\Temp\\TroyanEyes``. Fallback to the
    platform default temp directory when ``LOCALAPPDATA`` is unavailable. The
    location is exported to common temp environment variables so child
    processes also use the stable directory instead of spawning new
    ``_MEIxxxx`` folders each run when bundled.
    """

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        base_dir = Path(local_appdata) / "Temp" / TEMP_FOLDER_NAME
    else:
        base_dir = Path(tempfile.gettempdir()) / TEMP_FOLDER_NAME

    base_dir.mkdir(parents=True, exist_ok=True)

    # Keep temp usage consistent for this process and any children.
    for env_var in ("TMP", "TEMP", "TMPDIR"):
        os.environ[env_var] = str(base_dir)

    _cleanup_pyinstaller_temp(base_dir)

    return base_dir


def _cleanup_pyinstaller_temp(base_dir: Path) -> None:
    """Remove leftover PyInstaller temp folders such as ``_MEI*``.

    Stale extraction folders accumulate when PyInstaller cannot reuse the same
    temp path. This cleanup keeps only the active extraction directory (when
    running frozen) and the shared ``TroyanEyes`` temp folder, so bundled
    dependencies such as NumPy or Qt can coexist without spawning multiple
    ``_MEI`` directories.
    """
    # Check both the parent (system temp) and our base_dir (in case children extracted there)
    dirs_to_check = [base_dir.parent, base_dir]

    active_meipass = None
    if hasattr(sys, "_MEIPASS"):
        active_meipass = Path(sys._MEIPASS).resolve()

    for parent in dirs_to_check:
        if not parent.exists():
            continue

        for entry in parent.iterdir():
            if not entry.is_dir():
                continue
            if not entry.name.startswith("_MEI"):
                continue

            # Resolve to absolute path for comparison
            try:
                entry_resolved = entry.resolve()
            except OSError:
                continue

            # Skip the currently active bundle
            if active_meipass and entry_resolved == active_meipass:
                continue

            # Skip the shared temp dir itself (unlikely to match _MEI, but for safety)
            if entry_resolved == base_dir.resolve():
                continue

            try:
                shutil.rmtree(entry, ignore_errors=True)
            except Exception:
                pass