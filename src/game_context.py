import ctypes
import ctypes.wintypes
import threading
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

class GameContext:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GameContext, cls).__new__(cls)
                cls._instance.pid = None
                cls._instance.hwnd = None
        return cls._instance

    def set_process(self, pid):
        self.pid = pid
        self.hwnd = None
        # Try to find the window immediately, but it might take a moment to appear
        self._find_window()

    def _find_window(self):
        if self.pid is None:
            return None
        
        found_hwnd = None
        
        def callback(hwnd, _):
            nonlocal found_hwnd
            lpdw_process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_process_id))
            if lpdw_process_id.value == self.pid:
                # Check if it's a visible window (not a background worker)
                if user32.IsWindowVisible(hwnd):
                    found_hwnd = hwnd
                    return False # Stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
        
        self.hwnd = found_hwnd
        return self.hwnd

    def get_window_rect(self):
        """Returns (left, top, right, bottom) or None"""
        if self.hwnd is None:
            if not self._find_window():
                return None
        
        # Verify window is still valid
        if not user32.IsWindow(self.hwnd):
            self.hwnd = None
            return None

        rect = ctypes.wintypes.RECT()
        if user32.GetWindowRect(self.hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        return None

game_context = GameContext()
