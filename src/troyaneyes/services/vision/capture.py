"""
Window capture utilities for TroyanEyes v2.

- Primary backend: DXCam (if available).
- Fallback backend: MSS.
- Target window is resolved by process name (default: "Senthia.exe"),
  not by PID.

Dependencies (pip):
    pip install dxcam mss psutil pywin32 numpy
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np

# --- Optional backends -------------------------------------------------------

try:
    import dxcam  # type: ignore[import]
except ImportError:  # pragma: no cover
    dxcam = None  # type: ignore[assignment]

try:
    import mss  # type: ignore[import]
except ImportError:  # pragma: no cover
    mss = None  # type: ignore[assignment]

# --- Windows / process utilities --------------------------------------------

import psutil
import win32gui
import win32process

logger = logging.getLogger(__name__)

Rect = Tuple[int, int, int, int]

# Default game executable name.
DEFAULT_PROCESS_NAME = "Senthia.exe"


# --------------------------------------------------------------------------- #
# Window discovery by process name
# --------------------------------------------------------------------------- #
def _iter_hwnds_for_process_name(process_name: str) -> List[int]:
    """
    Return a list of top-level window handles (HWND) whose owning process's
    executable name matches `process_name` (case-insensitive).

    Only visible, non-minimized windows are considered.
    """
    target = process_name.lower()
    matching_hwnds: List[int] = []

    def _callback(hwnd: int, extra) -> bool:
        # Ignore invisible or minimized windows.
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.IsIconic(hwnd):
            return True

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True

        try:
            proc = psutil.Process(pid)
            name = proc.name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True
        except Exception:
            return True

        if name == target:
            matching_hwnds.append(hwnd)

        # Continue enumeration.
        return True

    win32gui.EnumWindows(_callback, None)
    return matching_hwnds


def _get_client_rect_screen_coords(hwnd: int) -> Rect:
    """
    Get the client rectangle of a window in absolute screen coordinates.

    Returns:
        (left, top, right, bottom)
    """
    # Client area size in window coordinates.
    left_client, top_client, right_client, bottom_client = win32gui.GetClientRect(hwnd)

    # Top-left corner in screen coordinates.
    left_top_screen = win32gui.ClientToScreen(hwnd, (left_client, top_client))
    right_bottom_screen = win32gui.ClientToScreen(hwnd, (right_client, bottom_client))

    left, top = left_top_screen
    right, bottom = right_bottom_screen

    return int(left), int(top), int(right), int(bottom)


def find_window_and_region_by_process(
    process_name: str = DEFAULT_PROCESS_NAME,
) -> Tuple[int, Rect]:
    """
    Resolve the first suitable window for the given process name and return:
        (hwnd, (left, top, right, bottom))

    Raises:
        RuntimeError: if no suitable window is found.
    """
    hwnds = _iter_hwnds_for_process_name(process_name)
    if not hwnds:
        raise RuntimeError(f"No visible window found for process '{process_name}'")

    # For now: just pick the first matching window.
    hwnd = hwnds[0]
    rect = _get_client_rect_screen_coords(hwnd)

    left, top, right, bottom = rect
    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        raise RuntimeError(
            f"Client rect for window (hwnd={hwnd}) has non-positive size: "
            f"{rect}"
        )

    logger.info(
        "Using window hwnd=%d for process '%s' at region (L=%d, T=%d, R=%d, B=%d)",
        hwnd,
        process_name,
        left,
        top,
        right,
        bottom,
    )
    return hwnd, rect


# --------------------------------------------------------------------------- #
# GameCapture abstraction
# --------------------------------------------------------------------------- #
class GameCapture:
    """
    High-level capture helper for the Senthia window.

    Usage:
        cap = GameCapture()  # defaults to process "Senthia.exe"
        frame = cap.get_frame()  # numpy array (backend-dependent format)

    The backend is chosen as:
        - DXCam if available
        - otherwise MSS
        - raises RuntimeError if neither is available
    """

    def __init__(
        self,
        process_name: str = DEFAULT_PROCESS_NAME,
        prefer_dxcam: bool = True,
    ) -> None:
        self.process_name = process_name
        self.prefer_dxcam = prefer_dxcam

        self._hwnd: Optional[int] = None
        self._region: Optional[Rect] = None

        self._backend: Optional[str] = None  # "dxcam" or "mss"
        self._dx_camera = None
        self._mss_ctx = None

        # Initial discovery
        self.refresh_window_region()
        self._init_backend()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @property
    def hwnd(self) -> Optional[int]:
        """Currently selected window handle (if any)."""
        return self._hwnd

    @property
    def region(self) -> Optional[Rect]:
        """Current capture region (left, top, right, bottom) in screen coords."""
        return self._region

    def refresh_window_region(self) -> None:
        """
        Re-scan for the target process, pick its window, and compute region.

        Call this if:
        - the game was restarted, or
        - the window was recreated and your capture failed, or
        - you suspect something changed with the main window.
        """
        hwnd, region = find_window_and_region_by_process(self.process_name)
        self._hwnd = hwnd
        self._region = region

        # Reconfigure DXCam region if we are already using it.
        if self._backend == "dxcam" and dxcam is not None and self._region is not None:
            self._dx_camera = dxcam.create(region=self._region)
            logger.info("DXCam region updated to %s", self._region)

    def get_frame(self) -> np.ndarray:
        """
        Grab a single frame from the configured backend.

        Returns:
            numpy.ndarray

        Notes:
            - DXCam: typically returns BGRA (uint8).
            - MSS: returns BGRA (uint8).
        """
        if self._backend is None:
            self._init_backend()

        if self._backend == "dxcam":
            return self._grab_with_dxcam()
        elif self._backend == "mss":
            return self._grab_with_mss()
        else:
            raise RuntimeError("No capture backend initialized")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _init_backend(self) -> None:
        """Choose and initialize DXCam or MSS as the actual capture backend."""
        if self._region is None:
            raise RuntimeError("Capture region is not set (window not found)")

        backends_order: List[str]
        if self.prefer_dxcam:
            backends_order = ["dxcam", "mss"]
        else:
            backends_order = ["mss", "dxcam"]

        for backend_name in backends_order:
            if backend_name == "dxcam" and dxcam is not None:
                self._init_dxcam()
                return
            if backend_name == "mss" and mss is not None:
                self._init_mss()
                return

        raise RuntimeError(
            "No suitable capture backend available. "
            "Install dxcam or mss (plus required dependencies)."
        )

    def _init_dxcam(self) -> None:
        """Initialize DXCam backend."""
        if dxcam is None:
            raise RuntimeError("DXCam is not installed")

        if self._region is None:
            raise RuntimeError("Region must be set before initializing DXCam")

        self._dx_camera = dxcam.create(region=self._region)
        self._backend = "dxcam"
        logger.info("Initialized DXCam backend with region %s", self._region)

    def _init_mss(self) -> None:
        """Initialize MSS backend."""
        if mss is None:
            raise RuntimeError("MSS is not installed")

        self._mss_ctx = mss.mss()
        self._backend = "mss"
        logger.info("Initialized MSS backend")

    def _grab_with_dxcam(self) -> np.ndarray:
        """Grab a frame using DXCam."""
        if self._dx_camera is None:
            self._init_dxcam()

        frame = self._dx_camera.grab()
        if frame is None:
            raise RuntimeError("DXCam returned no frame")
        return frame

    def _grab_with_mss(self) -> np.ndarray:
        """Grab a frame using MSS."""
        if self._mss_ctx is None:
            self._init_mss()

        if self._region is None:
            raise RuntimeError("Region must be set before MSS capture")

        left, top, right, bottom = self._region
        width = right - left
        height = bottom - top

        monitor = {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
        }

        raw = self._mss_ctx.grab(monitor)
        frame = np.array(raw)  # BGRA uint8
        return frame


# --------------------------------------------------------------------------- #
# Simple manual test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        cap = GameCapture()  # defaults to process "Senthia.exe"
        frame = cap.get_frame()
        print("Captured frame shape:", getattr(frame, "shape", None))
    except Exception as exc:
        print("Capture test failed:", exc)
