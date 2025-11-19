# TroyanEyes

Non-invasive automation bot for Metin2.

**Project purpose:**
- **Overview:** TroyanEyes automates repetitive in‑game actions (farming, combat, boss runs) without modifying the game client.  
It ships with a lightweight  GUI and a modular architecture ready for future YOLOv8 integration.

**Requirements:**
- **Python:** 3.14+ (use the same interpreter used to create your virtual environment)
- **Dependencies:** listed in `requirements.txt`

**Build (Windows / PowerShell):**
1. Create and activate a virtual environment (recommended):

```powershell
py -m venv venv
.\venv\Scripts\activate
```

2. Install dependencies:

```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

3. Build the EXE locally:

```powershell
pyinstaller --onefile --noconsole --name MaKoBot src/main.py
```

## Roadmap / Future Work
- Integrate YOLOv8 for real‑time object detection
- Implement window‑attachment for direct game‑screen capture
- Add configuration UI for user‑defined macros
- Write comprehensive unit‑test suite
- Publish the package on PyPI

Big shoutout to Knapik for testing the tool
