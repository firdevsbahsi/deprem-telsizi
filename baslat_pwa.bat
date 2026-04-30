@echo off
chcp 65001 >nul
title AFAD Deprem PWA - Web Sunucu

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo ============================================================
echo  AFAD Deprem PWA Baslatiliyor...
echo.
echo  Bilgisayardan : http://localhost:5000
echo  Telefondan    : http://[bu-bilgisayar-IP]:5000
echo                  (telefon ayni Wi-Fi'de olmali)
echo.
echo  IP'yi ogrenmek icin yeni terminalde: ipconfig
echo  Telefondan acip "Ana ekrana ekle" -> PWA olur.
echo.
echo  Cikis: Ctrl+C
echo ============================================================
echo.

%PYTHON% web\app.py

echo.
echo Sunucu kapandi.
pause
