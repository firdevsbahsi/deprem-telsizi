# Windows 7 Uyumlu Surum

Bu klasor, Windows 7 isletim sistemi icin uyarlanmis deprem telsiz ve
meteorolojik uyari yazilimlarini icerir.

## Windows 7 Sorunlari ve Cozumleri

| Sorun | Cozum |
|-------|-------|
| Python 3.9+ Windows 7'de calismaz | Python 3.8.20 kullanilmali |
| SSL sertifika hatalari (HTTPS) | `certifi` kutuphanesi + ozel SSL adaptoru |
| `list[dict]` type hint hatasi | `from __future__ import annotations` + typing modulu |
| PowerShell eski surum | 3 farkli ses calma yontemi (otomatik fallback) |
| urllib3 2.0+ Python 3.8 desteklemez | urllib3 < 2.0 sabitlendi |
| edge-tts 7+ Python 3.10 istiyor | edge-tts < 7.0 sabitlendi |
| asyncio.run() sorunlari | Manuel event loop yonetimi |

## Kurulum

### 1. Python 3.8 Indirin

Windows 7 icin son desteklenen Python surumu **3.8.20**'dir:

https://www.python.org/downloads/release/python-3820/

> ONEMLI: Kurulumda **"Add Python to PATH"** kutusunu isaretleyin!
> Veya `python_indir.bat` ile otomatik indirin.

### 2. Kutuphaneleri Kurun

`kur.bat` dosyasini cift tiklayarak calistirin. Veya komut satirinda:

```
cd "Windows 7"
pip install -r requirements.txt
```

### 3. Calistirin

**Deprem Telsiz:**
- `baslat_deprem.bat` dosyasini cift tiklayin
- Veya: `python deprem_telsiz.py --baofeng`

**Meteorolojik Uyari:**
- `baslat_uyari.bat` dosyasini cift tiklayin
- Veya: `python sari_uyari.py --tek-sefer`

## Dosyalar

| Dosya | Aciklama |
|-------|----------|
| `deprem_telsiz.py` | AFAD deprem verisi + telsiz (Win7 uyumlu) |
| `sari_uyari.py` | MGM meteorolojik uyari (Win7 uyumlu) |
| `kur.bat` | Otomatik kurulum scripti |
| `baslat_deprem.bat` | Deprem telsiz baslatici |
| `baslat_uyari.bat` | Meteorolojik uyari baslatici |
| `requirements.txt` | Python 3.8 uyumlu kutuphane listesi |

## Ek Notlar

- PowerShell 3.0+ kurulu ise ses calma daha iyi calisir
  (varsayilan PS 2.0 ile de WMP fallback ile calisir)
- .NET Framework 3.5+ kurulu olmalidir (genelde Windows 7'de vardir)
- Internet baglantisi gereklidir (AFAD/MGM API + Edge TTS)
