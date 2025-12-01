# src/troyaneyes/services/input/mouse_controller.py
from __future__ import annotations

import time
import win32process
import win32api
import win32con
import ctypes


# WinAPI event constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004


class MouseController:
    """
    Reliable low-level mouse injection for Metin2.
    Works even when pydirectinput fails.
    """

    # ----------------------------------------------------------
    # MOVE
    # ----------------------------------------------------------
    @staticmethod
    def move_to(x: int, y: int) -> None:
        win32api.SetCursorPos((int(x), int(y)))
        time.sleep(0.02)

    # ----------------------------------------------------------
    # FOCUS WINDOW
    # ----------------------------------------------------------
    @staticmethod
    def force_focus(hwnd: int):
        try:
            # Get thread IDs
            fg_win = win32gui.GetForegroundWindow()
            fg_tid, _ = win32process.GetWindowThreadProcessId(fg_win)
            target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

            # Temporarily attach threads
            ctypes.windll.user32.AttachThreadInput(fg_tid, target_tid, True)

            # Bring game window forward
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetFocus(hwnd)
            win32gui.SetActiveWindow(hwnd)

            # Detach
            ctypes.windll.user32.AttachThreadInput(fg_tid, target_tid, False)

            time.sleep(0.05)

        except Exception as e:
            print("[AttachFocusError]", e)


    # ----------------------------------------------------------
    # CLICK
    # ----------------------------------------------------------
    @staticmethod
    def click(x: int, y: int, hwnd: int | None = None) -> None:

        # Ensure game window has focus
        if hwnd is not None:
            MouseController.force_focus(hwnd)

        # Move cursor
        win32api.SetCursorPos((int(x), int(y)))
        time.sleep(0.015)

        # Send real hardware-like click
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.015)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)
