import customtkinter as ctk
from typing import Callable, Optional

from troyaneyes.gui.pages.teleporter_page import TeleporterPage


class MainWindow(ctk.CTk):
    """
    Main application window.

    Tabs:
    - "Run exe": one-shot exe trigger.
    - "Teleporter": teleporter toggle on/off.
    """

    def __init__(self) -> None:
        super().__init__()

        self.title("TroyanEyes v2 — Minimal")
        self.geometry("350x500")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Optional callback that main.py can assign.
        # Called once per "Run exe" click.
        self.on_run_exe: Optional[Callable[[], None]] = None

        # --- Tab container ---
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        # Tabs
        self.tabs.add("Run exe")
        self.tabs.add("Teleporter")

        run_tab = self.tabs.tab("Run exe")
        teleporter_tab = self.tabs.tab("Teleporter")

        # --- Run exe tab content (no toggle) ---
        self.run_exe_button = ctk.CTkButton(
            run_tab,
            text="Run exe",
            width=170,
            height=80,
            fg_color="#3CB371",
            command=self._handle_run_exe_click,
        )
        self.run_exe_button.pack(pady=(20, 10))

        self.status_label = ctk.CTkLabel(
            run_tab,
            text="Status: Idle",
        )
        self.status_label.pack(pady=(0, 20))

        # --- Teleporter tab content (toggle on/off) ---
        self.teleporter_page = TeleporterPage(
            teleporter_tab,
            toggle_callback=self._on_teleporter_toggle,
        )
        self.teleporter_page.pack(fill="both", expand=True, padx=10, pady=10)

    # --- Public helpers ---

    def set_status(self, text: str) -> None:
        """Update the status label text on the 'Run exe' tab."""
        self.status_label.configure(text=text)

    # --- Internal event handlers ---

    def _handle_run_exe_click(self) -> None:
        """Handle one-shot Run exe button click."""
        print("Run exe button clicked")
        self.set_status("Status: exe triggered")

        # Notify external callback if provided.
        if self.on_run_exe is not None:
            self.on_run_exe()

    def _on_teleporter_toggle(self, enabled: bool) -> None:
        """
        Called when the Teleporter toggle button changes state.
        """
        if enabled:
            self.set_status("Status: Teleporter ON")
            print("Teleporter toggled ON")
        else:
            self.set_status("Status: Teleporter OFF")
            print("Teleporter toggled OFF")
