# src/troyaneyes/services/vision/teleporter_runner.py
from __future__ import annotations

import logging
import threading
import time
from typing import Optional, List

import cv2
import numpy as np
import pydirectinput

from troyaneyes.services.templates.teleporter_templates import (
    TeleporterTemplateRepository,
    TeleporterTemplate,
    BOSS_TEMPLATE_KEY,
)
from troyaneyes.services.vision.capture import GameCapture
from troyaneyes.services.input.mouse_controller import MouseController

logger = logging.getLogger(__name__)


class TeleporterRunner:
    """
    Background worker implementing Map Switch Cycle + GLOBAL boss indicator check.

    Boss lock mode:
        - After boss teleporter is clicked, bot enters a lock state.
        - Holds SPACE continuously using watchdog.
        - Exits when template disappears or timeout expires.
    """

    def __init__(self, process_name: str, template_repo=None, fps=10.0, match_threshold=0.8):
        self.process_name = process_name
        self.fps = fps
        self.match_threshold = match_threshold

        self._template_repo = template_repo or TeleporterTemplateRepository()
        self._capture: Optional[GameCapture] = None

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._map_order: List[str] = []
        self._cycle_index: int = 0

        # Boss lock attributes
        self.boss_lock_timeout_sec = 20
        self._in_boss_lock: bool = False
        self._boss_lock_start_time: float = 0.0

        # SPACE watchdog thread
        self._space_watchdog_thread: Optional[threading.Thread] = None
        self._space_watchdog_stop = threading.Event()

    # ------------------------------------------------------------------
    # PUBLIC CONFIG
    # ------------------------------------------------------------------

    def set_boss_lock_timeout(self, seconds: int) -> None:
        self.boss_lock_timeout_sec = max(1, int(seconds))

    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        # stop watchdog too
        self._space_watchdog_stop.set()

        if self._thread:
            self._thread.join(timeout=1.0)

    def set_map_order(self, order: List[str]) -> None:
        self._map_order = order[:]
        self._cycle_index = 0

    # ------------------------------------------------------------------

    def _ensure_capture(self) -> GameCapture:
        if self._capture is None:
            self._capture = GameCapture(process_name=self.process_name)
        return self._capture

    # ------------------------------------------------------------------

    def _run(self):
        try:
            capture = self._ensure_capture()
        except Exception as exc:
            logger.error("Could not init GameCapture: %s", exc)
            return

        interval = 1.0 / max(self.fps, 0.1)

        while not self._stop_event.is_set():
            start = time.time()
            try:
                frame = capture.get_frame()
            except Exception:
                try:
                    capture.refresh_window_region()
                    frame = capture.get_frame()
                except Exception:
                    time.sleep(1.0)
                    continue

            try:
                self._process_frame_cycle(frame)
            except Exception as exc:
                logger.error("Frame cycle error: %s", exc)

            elapsed = time.time() - start
            if interval - elapsed > 0:
                time.sleep(interval - elapsed)

    # ------------------------------------------------------------------
    # FRAME CYCLE + BOSS LOCK MODE
    # ------------------------------------------------------------------

    def _process_frame_cycle(self, frame: np.ndarray) -> None:
        # Boss lock overrides everything
        if self._in_boss_lock:
            self._continue_boss_lock(frame)
            return

        templates = self._template_repo.load_all()
        if not templates or not self._map_order:
            return

        region = self._capture.region
        if region is None:
            return

        boss_tpl = templates.get(BOSS_TEMPLATE_KEY)
        boss_active = (
            boss_tpl
            and boss_tpl.snapshot is not None
            and boss_tpl.process_name.lower() == self.process_name.lower()
        )

        # Precompute grayscale once for map scanning
        frame_gray = self._to_gray(frame)

        # ----------------------------------------------------------------------
        # NEW LOGIC: scan ALL maps sequentially in one cycle
        # ----------------------------------------------------------------------
        for idx, map_name in enumerate(self._map_order):
            map_tpl = templates.get(map_name)

            if (
                not map_tpl
                or map_tpl.snapshot is None
                or map_tpl.process_name.lower() != self.process_name.lower()
            ):
                continue

            clicked = self._match_and_move(frame_gray, map_tpl, region, map_name)
            if not clicked:
                continue  # try the next map

            # Update cycle index (next map becomes first next iteration)
            self._cycle_index = (idx + 1) % len(self._map_order)

            # Wait for loading
            time.sleep(0.35)

            # Capture fresh frame after teleport
            try:
                new_frame = self._capture.get_frame()
                frame_gray = self._to_gray(new_frame)
            except Exception:
                return

            # --------------------------------------------------------------
            # Boss indicator scanning (multiple attempts)
            # --------------------------------------------------------------
            if boss_active:
                for _ in range(3):
                    boss_clicked = self._match_and_move(
                        frame_gray, boss_tpl, region, "BossIndicator"
                    )
                    if boss_clicked:
                        self._after_boss_teleport()
                        return

                    try:
                        new_frame = self._capture.get_frame()
                        frame_gray = self._to_gray(new_frame)
                    except Exception:
                        break

            # After finishing 1 map (including boss scan), continue to next map
            # DO NOT return — allows scanning ALL maps in one frame
            continue

    # ------------------------------------------------------------------

    @staticmethod
    def _to_gray(frame):
        bgr = frame[..., :3] if frame.shape[2] == 4 else frame
        rgb = bgr[..., ::-1]
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # ------------------------------------------------------------------

    def _match_and_move(self, frame_gray, template, window_region, name: str) -> bool:
        snapshot = template.snapshot
        th, tw = snapshot.shape[:2]
        fh, fw = frame_gray.shape[:2]
        if th > fh or tw > fw:
            return False

        res = cv2.matchTemplate(frame_gray, snapshot, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val < self.match_threshold:
            return False

        win_left, win_top, _, _ = window_region
        lx, ly = max_loc

        offset_x = 45
        center_x = win_left + lx + tw // 2 + offset_x
        center_y = win_top + ly + th // 2

        hwnd = self._capture.hwnd
        MouseController.move_to(center_x, center_y)
        MouseController.click(center_x, center_y, hwnd)

        time.sleep(0.10)
        print(f"[DEBUG] region={window_region}, max_loc={max_loc}, tpl_size={tw}x{th}")

        print(f"[Teleporter] '{name}' clicked at {center_x},{center_y}, score={max_val:.3f}")
        return True

    # ------------------------------------------------------------------
    # BOSS LOCK MODE
    # ------------------------------------------------------------------

    def _after_boss_teleport(self) -> None:
        """
        Enter boss lock mode:
            - Press '4'
            - Hold SPACE
            - Start watchdog to ensure SPACE stays held
        """
        time.sleep(3)
        pydirectinput.press('4')
        print("[Teleporter] Key '4' pressed")

        pydirectinput.keyDown('space')
        print("[Teleporter] Spacebar held down")

        self._in_boss_lock = True
        self._boss_lock_start_time = time.time()

        self._start_space_watchdog()

    # ------------------------------------------------------------------

    def _start_space_watchdog(self) -> None:
        """Continuously reassert keyDown('space') every 150 ms."""
        if self._space_watchdog_thread and self._space_watchdog_thread.is_alive():
            return

        self._space_watchdog_stop.clear()
        self._space_watchdog_thread = threading.Thread(
            target=self._space_watchdog_loop,
            daemon=True,
        )
        self._space_watchdog_thread.start()

    def _space_watchdog_loop(self):
        while not self._space_watchdog_stop.is_set():
            try:
                pydirectinput.keyDown('space')
            except Exception:
                pass
            time.sleep(0.15)

    # ------------------------------------------------------------------

    def _continue_boss_lock(self, frame: np.ndarray) -> None:
        templates = self._template_repo.load_all()
        boss_tpl = templates.get(BOSS_TEMPLATE_KEY)

        if not boss_tpl or boss_tpl.snapshot is None:
            self._exit_boss_lock("Missing boss template")
            return

        region = self._capture.region
        if region is None:
            self._exit_boss_lock("Region lost")
            return

        now = time.time()
        if now - self._boss_lock_start_time >= self.boss_lock_timeout_sec:
            self._exit_boss_lock("Timeout expired")
            return

        frame_gray = self._to_gray(frame)
        still_here = self._template_visible(frame_gray, boss_tpl)

        if not still_here:
            self._exit_boss_lock("Indicator disappeared")
            return

        # watchdog already keeps SPACE down
        time.sleep(0.10)

    # ------------------------------------------------------------------

    def _template_visible(self, frame_gray: np.ndarray, tpl: TeleporterTemplate) -> bool:
        snapshot = tpl.snapshot
        th, tw = snapshot.shape[:2]

        try:
            res = cv2.matchTemplate(frame_gray, snapshot, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            return max_val >= self.match_threshold
        except Exception:
            return False

    # ------------------------------------------------------------------

    def _exit_boss_lock(self, reason: str) -> None:
        print(f"[Teleporter] Boss lock ended: {reason}")
        self._in_boss_lock = False

        self._space_watchdog_stop.set()

        try:
            pydirectinput.keyUp('space')
        except Exception:
            pass

        # Reset for next cycle
        self._boss_lock_start_time = 0.0
