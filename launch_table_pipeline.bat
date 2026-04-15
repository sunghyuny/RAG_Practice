@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m rag_system.table_pipeline.launcher
) else (
    python -m rag_system.table_pipeline.launcher
)

endlocal
