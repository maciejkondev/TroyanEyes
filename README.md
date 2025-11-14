# KoniuBot

Non-invasive automation bot for Metin2.

**Project purpose:**
- **Overview:** KoniuBot includes a Python application with a main runtime and a patcher component that operates based on GitHub releases

**Requirements:**
- **Python:** 3.13+ (use the same interpreter used to create your virtual environment)
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

Big shoutout to Knapik for testing the tool
