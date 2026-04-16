@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m table_pipeline.launcher
) else (
    python -m table_pipeline.launcher
)

endlocal
