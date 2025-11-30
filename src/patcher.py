import sys
import os
import requests
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                               QProgressBar, QPushButton, QMessageBox)
from PySide6.QtCore import QThread, Signal, Qt

from utils.temp_dir import initialize_temp_dir
TEMP_DIR = initialize_temp_dir()

# Configuration
GITHUB_API_URL = "https://api.github.com/repos/maciejkondev/TroyanEyes/releases"
TARGET_DIR = "."
REQUIRED_FILES = ["TroyanEyes.exe", "TEPatcher.exe", "summon_window.pt", "boss_detector.pt"]
CURRENT_EXE = os.path.basename(sys.argv[0]).lower()

class DownloadWorker(QThread):
    progress = Signal(str, int)  # current_file, percent
    finished = Signal()
    error = Signal(str)
    log = Signal(str)
    version_found = Signal(str)
    restart_required = Signal()

    def run(self):
        try:
            # 1. Get Releases Info
            self.log.emit("Checking for updates...")
            try:
                resp = requests.get(GITHUB_API_URL)
                resp.raise_for_status()
                releases = resp.json()
                if not releases:
                    self.error.emit("No releases found.")
                    return
            except Exception as e:
                self.error.emit(f"Failed to fetch release info:\n{e}")
                return

            # Assume first one is latest
            latest_release = releases[0]
            tag_name = latest_release.get("tag_name", "Unknown")
            self.log.emit(f"Found latest release: {tag_name}")
            self.version_found.emit(tag_name)

            # 2. Prepare Target Directory
            if not os.path.exists(TARGET_DIR):
                os.makedirs(TARGET_DIR)

            # 3. Download Files
            downloaded_count = 0

            for target_file in REQUIRED_FILES:
                # Find asset in releases (newest first)
                asset = None
                found_version = None
                
                for release in releases:
                    assets = release.get("assets", [])
                    found = next((a for a in assets if a["name"] == target_file), None)
                    if found:
                        asset = found
                        found_version = release.get("tag_name")
                        break
                
                if not asset:
                    self.log.emit(f"Warning: {target_file} not found in any recent release.")
                    continue

                if found_version != tag_name:
                     self.log.emit(f"Found {target_file} in release {found_version}")

                download_url = asset["browser_download_url"]
                remote_size = asset.get("size", 0)
                
                # Determine save path
                save_path = os.path.join(TARGET_DIR, target_file)
                
                # Special handling for .pt files (weights)
                if target_file.endswith(".pt"):
                    possible_paths = [
                        os.path.join(TARGET_DIR, "data", "weights", target_file),
                        os.path.join(TARGET_DIR, "src", "data", "weights", target_file),
                        os.path.join(TARGET_DIR, "_internal", "data", "weights", target_file), # PyInstaller one-dir
                    ]
                    for p in possible_paths:
                        # If directory exists, assume that's the target (even if file doesn't exist yet)
                        if os.path.exists(os.path.dirname(p)):
                            save_path = p
                            break
                    # If file already exists in a specific location, prefer that
                    for p in possible_paths:
                        if os.path.exists(p):
                            save_path = p
                            break
                
                # SELF-UPDATE LOGIC
                is_self_update = False
                if target_file.lower() == CURRENT_EXE:
                    # Only if running as frozen exe (not python script)
                    if getattr(sys, 'frozen', False):
                        local_size = os.path.getsize(sys.executable)
                        if local_size != remote_size:
                            self.log.emit(f"Self-update detected for {target_file}...")
                            is_self_update = True
                            
                            # Rename current exe to .old
                            try:
                                old_path = sys.executable + ".old"
                                if os.path.exists(old_path):
                                    os.remove(old_path) # Try to remove previous backup
                                os.rename(sys.executable, old_path)
                                self.log.emit("Renamed current executable to .old")
                            except Exception as e:
                                self.error.emit(f"Failed to rename for update: {e}")
                                return
                        else:
                            self.log.emit(f"Skipping {target_file}: already up to date.")
                            self.progress.emit(target_file, 100)
                            continue
                    else:
                        self.log.emit(f"Skipping {target_file}: cannot update running script.")
                        continue

                # Check if file exists and size matches (skip if not self-update)
                if not is_self_update and os.path.exists(save_path):
                    local_size = os.path.getsize(save_path)
                    if local_size == remote_size and remote_size > 0:
                        self.log.emit(f"Skipping {target_file}: already up to date.")
                        self.progress.emit(target_file, 100)
                        continue
                
                self.log.emit(f"Downloading {target_file}...")
                
                try:
                    with requests.get(download_url, stream=True) as r:
                        r.raise_for_status()
                        total_length = r.headers.get('content-length')
                        
                        if total_length is None: # no content length header
                            with open(save_path, 'wb') as f:
                                f.write(r.content)
                            self.progress.emit(target_file, 100)
                        else:
                            dl = 0
                            total_length = int(total_length)
                            with open(save_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk:
                                        dl += len(chunk)
                                        f.write(chunk)
                                        percent = int(100 * dl / total_length)
                                        self.progress.emit(target_file, percent)
                    
                    downloaded_count += 1
                    self.log.emit(f"Successfully downloaded {target_file}")
                    
                    if is_self_update:
                        self.log.emit("Restarting patcher...")
                        self.restart_required.emit()
                        return # Stop processing, restart first
                    
                except Exception as e:
                    self.error.emit(f"Failed to download {target_file}:\n{e}")
                    return

            self.log.emit("All downloads finished.")
            self.finished.emit()

        except Exception as e:
            self.error.emit(f"Unexpected error:\n{e}")

class PatcherWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TroyanEyes Patcher")
        self.resize(400, 250)
        self.init_ui()
        self.cleanup_old_files()
        self.worker = None
        self.update_launch_button_state()

    def cleanup_old_files(self):
        """Try to remove .old files from previous updates"""
        if getattr(sys, 'frozen', False):
            old_path = sys.executable + ".old"
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    print(f"Cleaned up {old_path}")
                except:
                    pass

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.lbl_status = QLabel("Ready to update.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(self.lbl_status)

        self.lbl_version = QLabel("")
        self.lbl_version.setAlignment(Qt.AlignCenter)
        self.lbl_version.setStyleSheet("font-size: 12px; font-weight: bold; color: #2ecc71; margin-bottom: 10px;")
        layout.addWidget(self.lbl_version)

        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        self.pbar.setTextVisible(True)
        layout.addWidget(self.pbar)

        self.btn_start = QPushButton("Update files")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.start_patching)
        layout.addWidget(self.btn_start)

        self.btn_launch = QPushButton("Start TroyanEyes")
        self.btn_launch.setMinimumHeight(36)
        self.btn_launch.clicked.connect(self.start_troyaneyes)
        layout.addWidget(self.btn_launch)

        self.lbl_log = QLabel("")
        self.lbl_log.setStyleSheet("color: gray; font-size: 11px;")
        self.lbl_log.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_log)

        layout.addStretch()

    def start_patching(self):
        self.btn_start.setEnabled(False)
        self.btn_launch.setEnabled(False)
        self.pbar.setValue(0)
        self.lbl_version.setText("Checking version...")
        
        self.worker = DownloadWorker()
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_log)
        self.worker.error.connect(self.handle_error)
        self.worker.finished.connect(self.handle_finished)
        self.worker.version_found.connect(self.update_version)
        self.worker.restart_required.connect(self.handle_restart)
        self.worker.start()

    def update_progress(self, filename, percent):
        self.lbl_status.setText(f"Downloading {filename}...")
        self.pbar.setValue(percent)

    def update_version(self, version):
        self.lbl_version.setText(f"Latest Version: {version}")

    def update_log(self, message):
        self.lbl_log.setText(message)
        print(message)

    def handle_error(self, msg):
        QMessageBox.critical(self, "Error", msg)
        self.btn_start.setEnabled(True)
        self.btn_launch.setEnabled(True)
        self.lbl_status.setText("Update failed.")

    def handle_finished(self):
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("Up to date.")
        self.pbar.setValue(100)
        self.update_launch_button_state()
        
    def handle_restart(self):
        self.lbl_status.setText("Restarting...")
        # Launch the new executable
        try:
            subprocess.Popen([sys.executable])
            sys.exit(0)
        except Exception as e:
            QMessageBox.critical(self, "Restart Error", f"Failed to restart:\n{e}")

    def update_launch_button_state(self):
        exe_path = Path(TARGET_DIR) / "TroyanEyes.exe"
        self.btn_launch.setEnabled(exe_path.exists())

    def start_troyaneyes(self):
        exe_path = Path(TARGET_DIR) / "TroyanEyes.exe"
        if not exe_path.exists():
            QMessageBox.warning(self, "Missing executable", "TroyanEyes.exe was not found in the current directory.")
            self.btn_launch.setEnabled(False)
            return

        try:
            subprocess.Popen([str(exe_path)], cwd=TARGET_DIR)
            self.lbl_status.setText("Launched TroyanEyes.")
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to start TroyanEyes.exe:\n{e}")

if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    window = PatcherWindow()
    window.show()
    sys.exit(app.exec())
