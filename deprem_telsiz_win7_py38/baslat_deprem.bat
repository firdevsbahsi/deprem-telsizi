@echo off
chcp 65001 >nul
echo ============================================
echo   AFAD Deprem -> Baofeng Telsiz [Win7]
echo   Kapatmak icin Ctrl+C
echo ============================================
echo.
cd /d "%~dp0"
python deprem_telsiz.py --baofeng
pause
