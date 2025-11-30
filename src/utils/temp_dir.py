import os
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

    return base_dir
