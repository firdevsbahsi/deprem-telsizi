@echo off
chcp 65001 >nul
echo ============================================
echo   MGM Meteorolojik Uyari - Telsiz Sistemi
echo   Anons Saatleri: 10:00, 12:00, 14:00, 16:00
echo   Kapatmak icin Ctrl+C
echo ============================================
echo.
cd /d "%~dp0"

REM Ana projedeki venv varsa onu kullan
if exist "..\\.venv\\Scripts\\python.exe" (
    ..\.venv\Scripts\python.exe sari_uyari.py
) else (
    python sari_uyari.py
)
pause
