from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional, List

import numpy as np
from PIL import Image, ImageTk
from pathlib import Path

from troyaneyes.services.vision.capture import GameCapture, DEFAULT_PROCESS_NAME
from troyaneyes.services.vision.teleporter_runner import TeleporterRunner
from troyaneyes.services.templates.teleporter_templates import (
    TeleporterTemplate,
    TeleporterTemplateRepository,
    BOSS_TEMPLATE_KEY,
)
from troyaneyes.services.profile_store import ProfileStore


# ============================================================================ #
# Screenshot Window                                                           #
# ============================================================================ #

class ScreenshotWindow(ctk.CTkToplevel):
    """
    Allows selecting a rectangle on a captured game frame and saving it
    as a template snapshot (gray) for a target name.
    """

    def __init__(
        self,
        parent,
        frame: np.ndarray,
        title: str,
        template_name: str,
        process_name: str,
        template_repo: TeleporterTemplateRepository,
    ) -> None:
        super().__init__(parent)

        self.title(title)
        self._template_name = template_name
        self._process_name = process_name
        self._template_repo = template_repo

        self._start_x: Optional[int] = None
        self._start_y: Optional[int] = None
        self._rect_id: Optional[int] = None
        self._selection_rect: Optional[tuple[int, int, int, int]] = None

        image = self._frame_to_pil(frame)
        self._image_width, self._image_height = image.size

        self._pil_image = image
        self._gray_image = self._pil_image.convert("L")
        self._photo_image = ImageTk.PhotoImage(image)

        self.canvas = tk.Canvas(
            self,
            width=self._image_width,
            height=self._image_height,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self._photo_image, anchor="nw")

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", pady=(4, 8))

        ctk.CTkButton(
            bottom, text="Save template", command=self._on_save_template
        ).pack(side="right", padx=(0, 10))

        ctk.CTkButton(
            bottom,
            text="Cancel",
            fg_color="#444444",
            hover_color="#555555",
            command=self.destroy,
        ).pack(side="right", padx=(10, 10))

        self.geometry(f"{self._image_width}x{self._image_height + 40}")
        self.transient(parent)
        self.grab_set()

    @staticmethod
    def _frame_to_pil(frame: np.ndarray) -> Image.Image:
        if frame.ndim != 3:
            raise ValueError("Unexpected frame shape")
        bgr = frame[..., :3] if frame.shape[2] == 4 else frame
        rgb = bgr[..., ::-1]
        return Image.fromarray(rgb)

    # ------------------------------------------------------------------ #
    # Selection events
    # ------------------------------------------------------------------ #

    def _on_mouse_down(self, event: tk.Event) -> None:
        self._start_x = int(event.x)
        self._start_y = int(event.y)
        if self._rect_id:
            self.canvas.delete(self._rect_id)
        self._rect_id = None
        self._selection_rect = None

    def _on_mouse_drag(self, event: tk.Event) -> None:
        if self._start_x is None:
            return
        if self._rect_id:
            self.canvas.delete(self._rect_id)
        self._rect_id = self.canvas.create_rectangle(
            self._start_x,
            self._start_y,
            int(event.x),
            int(event.y),
            outline="red",
            width=2,
        )

    def _on_mouse_up(self, event: tk.Event) -> None:
        if self._start_x is None:
            return

        x1 = int(min(self._start_x, event.x))
        y1 = int(min(self._start_y, event.y))
        x2 = int(max(self._start_x, event.x))
        y2 = int(max(self._start_y, event.y))

        if x2 > x1 and y2 > y1:
            self._selection_rect = (x1, y1, x2, y2)
        else:
            if self._rect_id:
                self.canvas.delete(self._rect_id)
            self._rect_id = None
            self._selection_rect = None

    def _extract_snapshot(self, rect) -> np.ndarray:
        x1, y1, x2, y2 = rect
        return np.array(self._gray_image.crop((x1, y1, x2, y2)), dtype=np.uint8)

    # ------------------------------------------------------------------ #

    def _on_save_template(self) -> None:
        if not self._selection_rect:
            messagebox.showwarning("No selection", "Select a rectangle first.")
            return

        tpl = TeleporterTemplate(
            name=self._template_name,
            rect=self._selection_rect,
            image_size=(self._image_width, self._image_height),
            process_name=self._process_name,
            snapshot=self._extract_snapshot(self._selection_rect),
        )

        try:
            self._template_repo.save_template(tpl)
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))
            return

        messagebox.showinfo("Saved", f"Template '{self._template_name}' saved.")
        self.destroy()


# ============================================================================ #
# Teleporter Page                                                              #
# ============================================================================ #

class TeleporterPage(ctk.CTkFrame):
    """
    Teleporter tab:
    - Persistent map list (profile.json)
    - Template editing
    - Boss indicator editing
    - TeleporterRunner management
    """

    def __init__(
        self,
        parent,
        toggle_callback: Optional[Callable[[bool], None]] = None,
        template_repo: Optional[TeleporterTemplateRepository] = None,
    ) -> None:
        super().__init__(parent)

        self.toggle_callback = toggle_callback
        self._enabled = False
        self._items: List[ctk.CTkFrame] = []
        self._drag_item: Optional[ctk.CTkFrame] = None

        self._game_capture: Optional[GameCapture] = None
        self._template_repo = template_repo or TeleporterTemplateRepository()
        self._runner: Optional[TeleporterRunner] = None

        # persistence
        self._profile = ProfileStore()

        self._build_ui()
        self._load_map_order_from_profile()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        ctk.CTkLabel(self, text="Teleporter Farming").pack(pady=(10, 5))

        # Process name
        row = ctk.CTkFrame(self)
        row.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(row, text="Process name:").pack(side="left", padx=(0, 5))

        self.process_entry = ctk.CTkEntry(row, placeholder_text=DEFAULT_PROCESS_NAME)
        self.process_entry.pack(side="left", fill="x", expand=True)
        self.process_entry.insert(0, DEFAULT_PROCESS_NAME)

        # Toggle
        self.toggle_button = ctk.CTkButton(
            self, text="Turn on Teleporter", command=self._handle_toggle_click
        )
        self.toggle_button.pack(pady=(5, 10))

        # Boss indicator
        boss_row = ctk.CTkFrame(self)
        boss_row.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkButton(
            boss_row,
            text="Edit Boss Indicator",
            fg_color="#444499",
            command=self._on_edit_boss_indicator,
        ).pack(fill="x", pady=4)

        # Add map item
        addrow = ctk.CTkFrame(self)
        addrow.pack(fill="x", padx=10, pady=5)

        self.item_entry = ctk.CTkEntry(addrow, placeholder_text="Add teleporter target...")
        self.item_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(addrow, text="Add", width=70, command=self._on_add_item).pack(
            side="right"
        )

        ctk.CTkLabel(
            self,
            text="List of maps (drag to reorder priority):",
            anchor="w",
        ).pack(fill="x", padx=10)

        self.list_frame = ctk.CTkScrollableFrame(self, width=320, height=160)
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _load_map_order_from_profile(self) -> None:
        order = self._profile.load_map_order()
        for name in order:
            self._create_item_row(name)

    def _persist_map_order(self) -> None:
        self._profile.save_map_order(self.get_items())

    # ------------------------------------------------------------------ #
    # Capture
    # ------------------------------------------------------------------ #

    def get_items(self) -> list[str]:
        result = []
        for row in self._items:
            label = getattr(row, "_label", None)
            if label:
                result.append(label.cget("text"))
        return result

    def _get_process_name(self) -> str:
        txt = self.process_entry.get().strip()
        return txt if txt else DEFAULT_PROCESS_NAME

    def _get_or_create_capture(self) -> Optional[GameCapture]:
        if self._game_capture:
            return self._game_capture
        try:
            self._game_capture = GameCapture(process_name=self._get_process_name())
            return self._game_capture
        except Exception as exc:
            messagebox.showerror("Capture error", str(exc))
            return None

    # ------------------------------------------------------------------ #
    # Toggle Runner
    # ------------------------------------------------------------------ #

    def _handle_toggle_click(self) -> None:
        self._enabled = not self._enabled

        if self._enabled:
            self.toggle_button.configure(text="Turn off Teleporter farming")
            self._start_runner()
        else:
            self.toggle_button.configure(text="Turn on Teleporter")
            self._stop_runner()

        if self.toggle_callback:
            self.toggle_callback(self._enabled)

    def _start_runner(self) -> None:
        process = self._get_process_name()
        order = self.get_items()

        if self._runner and self._runner.process_name == process:
            self._runner.set_map_order(order)
            self._runner.start()
            return

        if self._runner:
            self._runner.stop()

        self._runner = TeleporterRunner(
            process_name=process,
            template_repo=self._template_repo,
            fps=10.0,
        )
        self._runner.set_map_order(order)
        self._runner.start()

    def _stop_runner(self) -> None:
        if self._runner:
            self._runner.stop()
        self._runner = None

    # ------------------------------------------------------------------ #
    # Boss Indicator
    # ------------------------------------------------------------------ #

    def _on_edit_boss_indicator(self) -> None:
        capture = self._get_or_create_capture()
        if not capture:
            return

        try:
            frame = capture.get_frame()
        except Exception:
            try:
                capture.refresh_window_region()
                frame = capture.get_frame()
            except Exception as exc:
                messagebox.showerror("Capture error", str(exc))
                return

        ScreenshotWindow(
            parent=self,
            frame=frame,
            title="Boss Indicator Template",
            template_name=BOSS_TEMPLATE_KEY,
            process_name=capture.process_name,
            template_repo=self._template_repo,
        )

    # ------------------------------------------------------------------ #
    # Map Items
    # ------------------------------------------------------------------ #

    def _on_add_item(self) -> None:
        text = self.item_entry.get().strip()
        if not text:
            return
        self.item_entry.delete(0, "end")

        self._create_item_row(text)
        self._persist_map_order()

        if self._enabled and self._runner:
            self._runner.set_map_order(self.get_items())

    def _create_item_row(self, text: str) -> None:
        row = ctk.CTkFrame(self.list_frame)
        row.pack(fill="x", padx=4, pady=2)

        # Drag handle
        handle = ctk.CTkLabel(row, text="≡", width=20)
        handle.pack(side="left", padx=(4, 4), pady=4)

        label = ctk.CTkLabel(row, text=text, anchor="w")
        label.pack(side="left", fill="x", expand=True, padx=(4, 4), pady=4)
        row._label = label

        ctk.CTkButton(
            row,
            text="Edit",
            width=50,
            command=lambda r=row: self._on_edit_item(r),
        ).pack(side="right", padx=4, pady=4)

        ctk.CTkButton(
            row,
            text="X",
            width=32,
            command=lambda r=row: self._remove_item(r),
        ).pack(side="right", padx=(4, 8), pady=4)

        # Drag support
        for w in (row, label, handle):
            w.bind("<Button-1>", lambda e, r=row: self._start_drag(e, r))
            w.bind("<B1-Motion>", lambda e, r=row: self._on_drag(e, r))
            w.bind("<ButtonRelease-1>", self._end_drag)

        self._items.append(row)

    def _remove_item(self, row: ctk.CTkFrame) -> None:
        if row in self._items:
            self._items.remove(row)
            row.destroy()

        self._persist_map_order()

        if self._enabled and self._runner:
            self._runner.set_map_order(self.get_items())

    # ------------------------------------------------------------------ #
    # Editing
    # ------------------------------------------------------------------ #

    def _get_row_text(self, row: ctk.CTkFrame) -> str:
        label = getattr(row, "_label", None)
        return label.cget("text") if label else ""

    def _on_edit_item(self, row: ctk.CTkFrame) -> None:
        name = self._get_row_text(row)
        capture = self._get_or_create_capture()
        if not capture:
            return

        try:
            frame = capture.get_frame()
        except Exception:
            try:
                capture.refresh_window_region()
                frame = capture.get_frame()
            except Exception as exc:
                messagebox.showerror("Capture error", str(exc))
                return

        ScreenshotWindow(
            parent=self,
            frame=frame,
            title=f"Template editor for: {name}",
            template_name=name,
            process_name=capture.process_name,
            template_repo=self._template_repo,
        )

    # ------------------------------------------------------------------ #
    # Drag & Drop (with persistence)
    # ------------------------------------------------------------------ #

    def _start_drag(self, event, row: ctk.CTkFrame) -> None:
        self._drag_item = row
        self.list_frame.update_idletasks()

    def _on_drag(self, event, row: ctk.CTkFrame) -> None:
        if self._drag_item is None or self._drag_item is not row:
            return

        mouse_y = event.y_root - self.list_frame.winfo_rooty()
        self.list_frame.update_idletasks()

        sorted_rows = sorted(self._items, key=lambda w: w.winfo_y())
        new_index = len(sorted_rows) - 1

        for idx, widget in enumerate(sorted_rows):
            mid = widget.winfo_y() + widget.winfo_height() // 2
            if mouse_y < mid:
                new_index = idx
                break

        current_index = self._items.index(row)

        if new_index != current_index:
            self._items.pop(current_index)
            self._items.insert(new_index, row)
            for w in self._items:
                w.pack_forget()
                w.pack(fill="x", padx=4, pady=2)

    def _end_drag(self, event) -> None:
        self._drag_item = None

        # persist order after drag end
        self._persist_map_order()

        if self._enabled and self._runner:
            self._runner.set_map_order(self.get_items())
