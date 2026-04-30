@echo off
chcp 65001 >nul
echo ============================================
echo   Windows 7 - AFAD Deprem Telsiz Kurulum
echo ============================================
echo.

REM Python kontrolu
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python yuklu degil!
    echo.
    echo Otomatik indirici baslatiliyor...
    call "%~dp0python_indir.bat"
    echo.
    echo Terminali kapatip yeniden acin, sonra kur.bat tekrar calistirin.
    pause
    exit /b
)

REM Python surum kontrolu
python -c "import sys; v=sys.version_info; exit(0 if v.major==3 and v.minor<=8 else 1)" 2>nul
if %errorlevel% neq 0 (
    echo [UYARI] Python 3.9+ Windows 7'de calismayabilir!
    echo Windows 7 icin Python 3.8.x kullanmaniz onerilir.
    echo https://www.python.org/downloads/release/python-3820/
    echo.
    echo Devam etmek icin bir tusa basin veya Ctrl+C ile iptal edin.
    pause
)

echo [1/3] pip guncelleniyor...
python -m pip install --upgrade pip -q

echo [2/3] Gerekli kutuphaneler kuruluyor...
pip install -r "%~dp0requirements.txt" -q

echo [3/3] Kurulum tamamlandi!
echo.
echo ============================================
echo   Kullanim:
echo   - Test:     python deprem_telsiz.py --baofeng --tek-sefer --adet 3
echo   - Calistir: python deprem_telsiz.py --baofeng
echo   - Uyari:    python sari_uyari.py --tek-sefer
echo ============================================
echo.
pause
