@echo off
chcp 65001 >nul
echo ============================================
echo   Windows 7 icin Python 3.8.20 Indirici
echo ============================================
echo.

REM Onceden kurulu mu kontrol et
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [BILGI] Python zaten kurulu:
    python --version
    echo.
    echo Yeniden indirmek istiyor musunuz?
    choice /c EH /m "E=Evet, H=Hayir"
    if errorlevel 2 goto :eof
)

echo Python 3.8.20 indiriliyor...
echo (Windows 7 icin son desteklenen surum)
echo.

REM PowerShell ile indir (Windows 7 PS 2.0+ uyumlu)
powershell -Command "& {$url='https://www.python.org/ftp/python/3.8.20/python-3.8.20-amd64.exe'; $out='%~dp0python-3.8.20-amd64.exe'; Write-Host 'Indiriliyor (64-bit)...'; (New-Object System.Net.WebClient).DownloadFile($url, $out); Write-Host 'Tamamlandi!'}" 2>nul

if not exist "%~dp0python-3.8.20-amd64.exe" (
    echo [UYARI] 64-bit indirilemedi, 32-bit deneniyor...
    powershell -Command "& {$url='https://www.python.org/ftp/python/3.8.20/python-3.8.20.exe'; $out='%~dp0python-3.8.20.exe'; Write-Host 'Indiriliyor (32-bit)...'; (New-Object System.Net.WebClient).DownloadFile($url, $out); Write-Host 'Tamamlandi!'}" 2>nul
)

echo.

if exist "%~dp0python-3.8.20-amd64.exe" (
    echo ============================================
    echo   Python 3.8.20 (64-bit) indirildi!
    echo   Dosya: python-3.8.20-amd64.exe
    echo ============================================
    echo.
    echo Simdi kurulum baslatilsin mi?
    echo (Add to PATH otomatik isaretlenecek)
    echo.
    choice /c EH /m "E=Kur, H=Sonra kurarım"
    if errorlevel 2 goto :bitti
    echo.
    echo Kurulum baslatiliyor...
    "%~dp0python-3.8.20-amd64.exe" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
    goto :bitti
)

if exist "%~dp0python-3.8.20.exe" (
    echo ============================================
    echo   Python 3.8.20 (32-bit) indirildi!
    echo   Dosya: python-3.8.20.exe
    echo ============================================
    echo.
    echo Simdi kurulum baslatilsin mi?
    echo (Add to PATH otomatik isaretlenecek)
    echo.
    choice /c EH /m "E=Kur, H=Sonra kurarım"
    if errorlevel 2 goto :bitti
    echo.
    echo Kurulum baslatiliyor...
    "%~dp0python-3.8.20.exe" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
    goto :bitti
)

echo [HATA] Python indirilemedi!
echo.
echo Manuel olarak indirin:
echo https://www.python.org/downloads/release/python-3820/
echo.
echo 64-bit: python-3.8.20-amd64.exe
echo 32-bit: python-3.8.20.exe

:bitti
echo.
echo Kurulum tamamlandiysa terminali kapatip yeniden acin,
echo sonra kur.bat dosyasini calistirin.
echo.
pause
