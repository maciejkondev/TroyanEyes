import sys
import os
import requests
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                               QProgressBar, QPushButton, QMessageBox)
from PySide6.QtCore import QThread, Signal, Qt

# Configuration
GITHUB_API_URL = "https://api.github.com/repos/maciejkondev/TroyanEyes/releases/latest"
TARGET_DIR = "."
REQUIRED_FILES = ["TroyanEyes.exe", "TEPatcher.exe", "model.pt"]

class DownloadWorker(QThread):
    progress = Signal(str, int)  # current_file, percent
    finished = Signal()
    error = Signal(str)
    log = Signal(str)

    def run(self):
        try:
            # 1. Get Release Info
            self.log.emit("Checking for updates...")
            try:
                resp = requests.get(GITHUB_API_URL)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                self.error.emit(f"Failed to fetch release info:\n{e}")
                return

            tag_name = data.get("tag_name", "Unknown")
            self.log.emit(f"Found latest release: {tag_name}")

            # 2. Prepare Target Directory
            if not os.path.exists(TARGET_DIR):
                os.makedirs(TARGET_DIR)

            # 3. Download Files
            assets = data.get("assets", [])
            downloaded_count = 0

            for target_file in REQUIRED_FILES:
                # Find asset url
                asset = next((a for a in assets if a["name"] == target_file), None)
                
                if not asset:
                    self.log.emit(f"Warning: {target_file} not found in release.")
                    continue

                download_url = asset["browser_download_url"]
                save_path = os.path.join(TARGET_DIR, target_file)
                
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
        self.resize(400, 200)
        self.init_ui()
        
        self.worker = None

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.lbl_status = QLabel("Ready to update.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(self.lbl_status)

        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        self.pbar.setTextVisible(True)
        layout.addWidget(self.pbar)

        self.btn_start = QPushButton("Update files")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.start_patching)
        layout.addWidget(self.btn_start)

        self.lbl_log = QLabel("")
        self.lbl_log.setStyleSheet("color: gray; font-size: 11px;")
        self.lbl_log.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_log)

        layout.addStretch()

    def start_patching(self):
        self.btn_start.setEnabled(False)
        self.pbar.setValue(0)
        
        self.worker = DownloadWorker()
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_log)
        self.worker.error.connect(self.handle_error)
        self.worker.finished.connect(self.handle_finished)
        self.worker.start()

    def update_progress(self, filename, percent):
        self.lbl_status.setText(f"Downloading {filename}...")
        self.pbar.setValue(percent)

    def update_log(self, message):
        self.lbl_log.setText(message)
        print(message)

    def handle_error(self, msg):
        QMessageBox.critical(self, "Error", msg)
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("Update failed.")

    def handle_finished(self):
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("Up to date.")
        self.pbar.setValue(100)

if __name__ == "__main__":

    
    app = QApplication(sys.argv)
    window = PatcherWindow()
    window.show()
    sys.exit(app.exec())
