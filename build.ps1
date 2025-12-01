$env:PYTHONPATH = "$PSScriptRoot\src"
$env:NUITKA_EXTRA_OPTIONS="--plugin-enable=tk-inter"

python -m nuitka `
  --standalone `
  --onefile `
  --msvc=latest `
  --windows-console-mode=hide `
  --follow-imports `
  --enable-plugin=tk-inter `
  --include-package=troyaneyes `
  --include-data-dir="src\troyaneyes=temp_dir_sources" `
  --include-data-dir="temp_dir=temp_dir" `
  src\troyaneyes\main.py
