@echo off
chcp 65001 >nul
title AFAD Deprem Telsiz

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set PYTHON=".venv\Scripts\python.exe"
) else (
    set PYTHON=python
)

echo ============================================================
echo  AFAD Deprem -^> Telsiz Sistemi Baslatiliyor...
echo  Cikis icin Ctrl+C
echo ============================================================
echo.

%PYTHON% deprem_telsiz.py --baofeng

echo.
echo Program sonlandi.
pause
