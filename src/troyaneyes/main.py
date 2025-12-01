from troyaneyes.gui.main_window import MainWindow
import os, sys
os.chdir(os.path.dirname(sys.executable))


def main() -> None:
    """
    Application entrypoint.
    Creates the main GUI window with:
    - "Run exe" tab: one-shot run trigger.
    - "Teleporter" tab: toggle on/off.
    """
    app = MainWindow()

    # Example external callback for "Run exe".
    def on_run_exe() -> None:
        print("Run exe callback triggered")
        app.set_status("Status: exe run requested")

    app.on_run_exe = on_run_exe

    app.mainloop()


if __name__ == "__main__":
    main()
