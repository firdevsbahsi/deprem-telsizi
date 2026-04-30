@echo off
chcp 65001 >nul
echo ============================================
echo   MGM Meteorolojik Uyari - Telsiz [Win7]
echo   Anons Saatleri: 10:00, 12:00, 14:00, 16:00
echo   Kapatmak icin Ctrl+C
echo ============================================
echo.
cd /d "%~dp0"
python sari_uyari.py
pause
