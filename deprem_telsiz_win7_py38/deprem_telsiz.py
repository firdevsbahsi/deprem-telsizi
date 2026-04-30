#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AFAD Son Depremler -> Telsiz Gönderici (Baofeng Destekli)
==========================================================
** Windows 7 Uyumlu Sürüm (Python 3.8) **

AFAD'dan son deprem verilerini çeker, yeni depremleri tespit eder
ve Baofeng telsiz üzerinden sesli olarak yayınlar.

Baofeng Modu (--baofeng):
  Deprem bilgisini Türkçe seslendirir, ses kartı çıkışından
  Baofeng'in mikrofon girişine kablo ile gönderir.
  Baofeng'de VOX aktif olmalı -> ses gelince otomatik yayın yapar.

Kullanım:
  python deprem_telsiz.py                        # Test modu (ekrana basar)
  python deprem_telsiz.py --baofeng               # Baofeng TTS modu
  python deprem_telsiz.py --baofeng --tek-sefer    # Sesli test (bir kez okur)
  python deprem_telsiz.py --port COM3              # Seri port modu (dijital telsiz)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import ssl
import sys
import time
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


# ── SSL Fix (Windows 7 sertifika sorunu) ────────────────────────────────────

class Win7SSLAdapter(HTTPAdapter):
    """Windows 7 için SSL uyumluluk adaptörü."""
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.load_verify_locations(certifi.where())
        # Eski TLS sürümlerini de kabul et
        ctx.options &= ~ssl.OP_NO_TLSv1
        ctx.options &= ~ssl.OP_NO_TLSv1_1
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def guvenli_session():
    """Windows 7 uyumlu requests session'ı oluşturur."""
    session = requests.Session()
    adapter = Win7SSLAdapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ── Ayarlar ──────────────────────────────────────────────────────────────────

AFAD_API_URL = "https://deprem.afad.gov.tr/apiv2/event/filter"
AFAD_API_URL_ALT = "https://servisnet.afad.gov.tr/apigateway/deprem/apiv2/event/filter"
AFAD_HTML_URL = "https://deprem.afad.gov.tr/last-earthquakes.html"
KANDILLI_URL = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"

VARSAYILAN_KONTROL_ARASI = 60       # saniye
VARSAYILAN_MIN_BUYUKLUK = 3.0       # 3.0 dahil ve üzeri
VARSAYILAN_BAUD_RATE = 9600
VARSAYILAN_MESAJ_GECIKMESI = 2      # mesajlar arası bekleme (sn)

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("deprem_telsiz")

# ── AFAD Veri Çekme ─────────────────────────────────────────────────────────


def _tarih_parse(tarih_str):
    """Tarih stringini datetime objesine cevirir."""
    try:
        s = str(tarih_str).strip()
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        # "2026.04.20 14:29:09" (Kandilli formati)
        if "." in s[:10] and len(s) >= 19:
            return datetime.strptime(s[:19], "%Y.%m.%d %H:%M:%S").replace(
                tzinfo=timezone(timedelta(hours=3))
            )
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone(timedelta(hours=3))
        )
    except Exception:
        return None


def _tarih_filtrele(depremler, son_saat):
    # type: (List[Dict], int) -> List[Dict]
    """Sadece son N saat icindeki depremleri filtreler."""
    if son_saat <= 0:
        return depremler

    tr_saat = timezone(timedelta(hours=3))
    simdi = datetime.now(tz=tr_saat)
    esik = simdi - timedelta(hours=son_saat)

    filtreli = []
    for d in depremler:
        dt = _tarih_parse(d["tarih"])
        if dt is None or dt >= esik:
            filtreli.append(d)

    if len(filtreli) != len(depremler):
        log.info("Tarih filtresi: %d -> %d deprem (son %d saat)",
                 len(depremler), len(filtreli), son_saat)
    return filtreli


def _tarihe_gore_sirala(depremler):
    # type: (List[Dict],) -> List[Dict]
    """Depremleri tarihe gore siralar (en yeni basta)."""
    def _sort_key(d):
        dt = _tarih_parse(d["tarih"])
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt

    return sorted(depremler, key=_sort_key, reverse=True)


def _tekrarlari_kaldir(depremler):
    # type: (List[Dict],) -> List[Dict]
    """AFAD ve Kandilli'den gelen ayni depremleri teke dusurur."""
    sonuc = []
    for d in depremler:
        dt = _tarih_parse(d["tarih"])
        tekrar = False
        for s in sonuc:
            st = _tarih_parse(s["tarih"])
            if dt and st:
                fark = abs((dt - st).total_seconds())
                try:
                    enlem_fark = abs(float(d["enlem"]) - float(s["enlem"]))
                    boylam_fark = abs(float(d["boylam"]) - float(s["boylam"]))
                except (ValueError, TypeError):
                    enlem_fark = boylam_fark = 999
                if fark < 120 and enlem_fark < 0.1 and boylam_fark < 0.1:
                    tekrar = True
                    break
        if not tekrar:
            sonuc.append(d)
    return sonuc


def deprem_verisi_cek(min_buyukluk=0.0, limit=100, son_saat=24):
    # type: (float, int, int) -> List[Dict]
    """AFAD + Kandilli'den deprem verisi ceker, birlestirir, tarihe gore siralar."""
    tum_depremler = []

    # 1) AFAD HTML
    afad = html_den_cek(min_buyukluk)
    if afad:
        log.info("AFAD: %d deprem", len(afad))
        tum_depremler.extend(afad)

    # 2) AFAD API (HTML basarisiz olduysa)
    if not afad:
        log.info("AFAD HTML basarisiz, API deneniyor...")
        afad_api = _afad_api_cek(min_buyukluk, limit)
        if afad_api:
            tum_depremler.extend(afad_api)

    # 3) Kandilli
    kandilli = kandilli_den_cek(min_buyukluk)
    if kandilli:
        log.info("Kandilli: %d deprem", len(kandilli))
        tum_depremler.extend(kandilli)

    if not tum_depremler:
        return []

    # Tekrar edenleri kaldir
    tum_depremler = _tekrarlari_kaldir(tum_depremler)

    # Tarihe gore sirala (en yeni basta)
    tum_depremler = _tarihe_gore_sirala(tum_depremler)

    return _tarih_filtrele(tum_depremler, son_saat)


def _afad_api_cek(min_buyukluk, limit):
    # type: (float, int) -> List[Dict]
    """AFAD API'den deprem verisi ceker."""
    tr_saat = timezone(timedelta(hours=3))
    bugun = datetime.now(tz=tr_saat)
    dun = bugun - timedelta(days=1)
    yarin = bugun + timedelta(days=1)

    params = {
        "start": dun.strftime("%Y-%m-%d"),
        "end": yarin.strftime("%Y-%m-%d"),
        "minmag": min_buyukluk,
        "maxmag": 10,
        "orderby": "timedesc",
        "limit": limit,
    }

    session = guvenli_session()

    for api_url in [AFAD_API_URL, AFAD_API_URL_ALT]:
        try:
            resp = session.get(api_url, params=params, timeout=15)
            resp.raise_for_status()
            veri = resp.json()

            depremler = []
            if isinstance(veri, list):
                for d in veri:
                    depremler.append({
                        "tarih": d.get("date", d.get("eventDate", "")),
                        "enlem": d.get("latitude", ""),
                        "boylam": d.get("longitude", ""),
                        "derinlik": d.get("depth", ""),
                        "buyukluk": float(d.get("magnitude", 0)),
                        "yer": d.get("location", d.get("province", "")),
                        "tip": d.get("magnitudeType", "ML"),
                        "kaynak": "AFAD",
                    })
                log.info("AFAD API: %d deprem", len(depremler))
                return depremler
        except Exception as e:
            log.warning("API hatasi (%s): %s", api_url, e)
    return []


def kandilli_den_cek(min_buyukluk=0.0):
    # type: (float,) -> List[Dict]
    """Kandilli Rasathanesi'nden son depremleri ceker (KOERI lst0.asp)."""
    import re

    session = guvenli_session()
    try:
        resp = session.get(KANDILLI_URL, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        metin = resp.text
    except Exception as e:
        log.warning("Kandilli baglanti hatasi: %s", e)
        return []

    depremler = []
    pattern = re.compile(
        r"(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2}:\d{2})\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
        r"[\d.-]+\s+([\d.-]+)\s+([\d.-]+)\s+"
        r"(.+?)\s{2,}"
    )

    for satir in metin.split("\n"):
        m = pattern.search(satir)
        if not m:
            continue

        tarih_str = m.group(1)
        saat_str = m.group(2)
        enlem = m.group(3)
        boylam = m.group(4)
        derinlik = m.group(5)
        ml = m.group(6)
        mw = m.group(7)
        yer = m.group(8).strip()

        try:
            ml_val = float(ml) if ml != "-.-" else 0.0
        except ValueError:
            ml_val = 0.0
        try:
            mw_val = float(mw) if mw != "-.-" else 0.0
        except ValueError:
            mw_val = 0.0
        buyukluk = max(ml_val, mw_val)

        if buyukluk < min_buyukluk:
            continue

        depremler.append({
            "tarih": "{} {}".format(tarih_str.replace(".", "-"), saat_str),
            "enlem": enlem,
            "boylam": boylam,
            "derinlik": derinlik,
            "buyukluk": buyukluk,
            "yer": yer,
            "tip": "Mw" if mw_val > ml_val else "ML",
            "kaynak": "Kandilli",
        })

    return depremler


def html_den_cek(min_buyukluk=0.0):
    # type: (float,) -> List[Dict]
    """AFAD HTML sayfasından son depremleri parse eder."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.error("bs4 (BeautifulSoup) yuklu degil. pip install beautifulsoup4")
        return []

    try:
        session = guvenli_session()
        resp = session.get(AFAD_HTML_URL, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        depremler = []
        tablo = soup.find("table")
        if not tablo:
            log.error("HTML'de tablo bulunamadi.")
            return []

        satirlar = tablo.find_all("tr")[1:]
        for satir in satirlar:
            hucreler = satir.find_all("td")
            if len(hucreler) >= 7:
                try:
                    buyukluk = float(hucreler[5].get_text(strip=True))
                except (ValueError, IndexError):
                    continue

                if buyukluk >= min_buyukluk:
                    depremler.append({
                        "tarih": hucreler[0].get_text(strip=True),
                        "enlem": hucreler[1].get_text(strip=True),
                        "boylam": hucreler[2].get_text(strip=True),
                        "derinlik": hucreler[3].get_text(strip=True),
                        "buyukluk": buyukluk,
                        "yer": hucreler[6].get_text(strip=True),
                        "tip": hucreler[4].get_text(strip=True),
                    })

        for dep in depremler:
            dep["kaynak"] = "AFAD"

        log.info("HTML'den %d deprem cekildi.", len(depremler))
        return depremler

    except Exception as e:
        log.error("HTML cekme hatasi: %s", e)
        return []


# ── Mesaj Formatlama ─────────────────────────────────────────────────────────


def _tarih_saat_al(tarih_str):
    """Tarih stringinden saat:dakika çıkarır."""
    try:
        if "T" in str(tarih_str):
            dt = datetime.fromisoformat(str(tarih_str).replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(str(tarih_str)[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M")
    except Exception:
        return str(tarih_str)[-8:-3] if len(str(tarih_str)) > 8 else str(tarih_str)


def _tarih_gun_al(tarih_str):
    """Tarih stringinden gun.ay cikarir (orn: 20.04)."""
    try:
        if "T" in str(tarih_str):
            dt = datetime.fromisoformat(str(tarih_str).replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(str(tarih_str)[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d.%m")
    except Exception:
        return ""


def telsiz_mesaji_olustur(deprem):
    # type: (Dict,) -> str
    """Deprem verisini telsiz metin formatına çevirir."""
    saat = _tarih_saat_al(deprem["tarih"])
    yer = turkce_ascii(deprem["yer"])

    return (
        "DEPREM! M{:.1f} | {} | {} | Derin:{}km | {}/{}".format(
            deprem["buyukluk"], saat, yer,
            deprem["derinlik"], deprem["enlem"], deprem["boylam"]
        )
    )


def sesli_mesaj_olustur(deprem):
    # type: (Dict,) -> str
    """Deprem verisini Türkçe sesli anons formatına çevirir."""
    saat = _tarih_saat_al(deprem["tarih"])
    buyukluk = deprem["buyukluk"]
    yer = deprem["yer"]
    kaynak = deprem.get("kaynak", "AFAD")

    if kaynak == "Kandilli":
        kurum = "Kandilli Rasathanesi verilerine gore"
    else:
        kurum = "Afet ve Acil Durum Baskanligi verilerine gore"

    return (
        "{} "
        "saat {} sularinda "
        "{} ve cevresinde "
        "{:.1f} buyuklugunde yer sarsintisi meydana gelmistir.".format(
            kurum, saat, yer, buyukluk
        )
    )


def turkce_ascii(metin):
    # type: (str,) -> str
    """Türkçe karakterleri ASCII karşılıklarına çevirir."""
    tr_map = str.maketrans(
        "çÇğĞıİöÖşŞüÜ",
        "cCgGiIoOsSuU"
    )
    return metin.translate(tr_map)


# ── Ses Çalma (Windows 7 Uyumlu) ────────────────────────────────────────────


def ses_dosya_cal(dosya_yolu):
    """MP3 dosyasını Windows 7 uyumlu şekilde çalar.
    
    Sırasıyla dener:
    1. PowerShell MediaPlayer (.NET 3.5+)
    2. Windows Media Player (wmplayer)
    3. start komutu (varsayılan uygulama)
    """
    dosya_yolu = os.path.abspath(dosya_yolu)

    # Yöntem 1: PowerShell MediaPlayer
    try:
        ps_script = (
            '[System.Reflection.Assembly]::LoadWithPartialName("PresentationCore") | Out-Null; '
            '$p = New-Object System.Windows.Media.MediaPlayer; '
            '$p.Open([Uri]::new("{}")); '.format(dosya_yolu) +
            'Start-Sleep -Milliseconds 800; '
            '$p.Play(); '
            '$timeout = 0; '
            'while($p.NaturalDuration.HasTimeSpan -eq $false -and $timeout -lt 50){Start-Sleep -Milliseconds 200; $timeout++}; '
            'if($p.NaturalDuration.HasTimeSpan){'
            '  $dur = [int]$p.NaturalDuration.TimeSpan.TotalSeconds + 2; '
            '  Start-Sleep -Seconds $dur'
            '} else { Start-Sleep -Seconds 30 }; '
            '$p.Stop(); $p.Close()'
        )
        result = subprocess.run(
            ["powershell", "-sta", "-NoProfile", "-c", ps_script],
            timeout=120,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        log.warning("PowerShell MediaPlayer basarisiz, alternatif deneniyor...")
    except Exception as e:
        log.warning("PowerShell hatasi: %s, alternatif deneniyor...", e)

    # Yöntem 2: Windows Media Player ile çal
    try:
        wmplayer = os.path.join(
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            "Windows Media Player", "wmplayer.exe"
        )
        if not os.path.exists(wmplayer):
            wmplayer = os.path.join(
                os.environ.get("ProgramFiles", r"C:\Program Files"),
                "Windows Media Player", "wmplayer.exe"
            )
        if os.path.exists(wmplayer):
            proc = subprocess.Popen(
                [wmplayer, "/play", "/close", dosya_yolu],
            )
            proc.wait(timeout=120)
            time.sleep(2)
            return
    except Exception as e:
        log.warning("WMP hatasi: %s", e)

    # Yöntem 3: start komutu ile varsayılan uygulama
    try:
        os.startfile(dosya_yolu)
        time.sleep(15)  # Tahmini bekleme
    except Exception as e:
        log.error("Ses calma tamamen basarisiz: %s", e)


# ── Gönderici Sınıfları ──────────────────────────────────────────────────────


class TelsizGonderici(object):
    """Seri port üzerinden telsize mesaj gönderir (dijital telsizler için)."""

    def __init__(self, port=None, baud=VARSAYILAN_BAUD_RATE,
                 mesaj_gecikmesi=VARSAYILAN_MESAJ_GECIKMESI):
        self.port = port
        self.baud = baud
        self.mesaj_gecikmesi = mesaj_gecikmesi
        self.ser = None
        self.test_modu = port is None

        if self.test_modu:
            log.info("TEST MODU: Seri port belirtilmedi, mesajlar ekrana basilacak.")
        else:
            if not SERIAL_AVAILABLE:
                log.error("pyserial yuklu degil! pip install pyserial")
                sys.exit(1)
            try:
                self.ser = serial.Serial(
                    port=port,
                    baudrate=baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=2,
                )
                log.info("Seri port acildi: %s @ %d baud", port, baud)
            except serial.SerialException as e:
                log.error("Seri port acilamadi: %s", e)
                sys.exit(1)

    def gonder(self, mesaj):
        if self.test_modu:
            print("  [TELSIZ] %s" % mesaj)
        else:
            veri = (mesaj + "\r\n").encode("ascii", errors="replace")
            self.ser.write(veri)
            self.ser.flush()
            log.info("Gonderildi (%d byte): %s", len(veri), mesaj[:60])
        time.sleep(self.mesaj_gecikmesi)

    def kapat(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            log.info("Seri port kapatildi.")


class BaofengGonderici(object):
    """Baofeng telsiz için doğal sesli anons gönderici (Edge TTS).

    Microsoft Edge TTS ile doğal Türkçe ses üretir.
    Ses dosyasını oluşturur ve çalar.
    """

    SESLER = {
        "erkek": "tr-TR-AhmetNeural",
        "kadin": "tr-TR-EmelNeural",
    }

    def __init__(self, ses_hizi="+0%", ses_tipi="erkek", mesaj_gecikmesi=2.0,
                 test_modu=False):
        self.mesaj_gecikmesi = mesaj_gecikmesi
        self.test_modu = test_modu
        self.ses_hizi = ses_hizi
        self.ses = self.SESLER.get(ses_tipi, self.SESLER["erkek"])
        self.ses_dosya = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_anons.mp3"
        )

        log.info("BAOFENG MODU: Dogal Turkce ses aktif (ses=%s, hiz=%s)",
                 self.ses, ses_hizi)
        if not test_modu:
            log.info("Baofeng'de VOX'un acik oldugundan emin olun!")

    def gonder(self, mesaj):
        """Metni doğal Türkçe sesle okur."""
        print("  [SES] %s" % mesaj)
        log.info("Seslendiriliyor: %s", mesaj[:80])

        if not self.test_modu:
            # 1) Edge TTS (en iyi kalite)
            try:
                self._ses_uret_ve_cal(mesaj)
                time.sleep(self.mesaj_gecikmesi)
                return
            except Exception as e:
                log.warning("Edge TTS hatasi: %s — gTTS deneniyor...", e)

            # 2) gTTS (Google TTS — iyi kalite)
            try:
                self._gtts_ile_oku(mesaj)
                time.sleep(self.mesaj_gecikmesi)
                return
            except Exception as e:
                log.warning("gTTS hatasi: %s — pyttsx3 deneniyor...", e)

            # 3) pyttsx3 (cevrimdisi — son care)
            try:
                self._pyttsx3_ile_oku(mesaj)
            except Exception as e2:
                log.error("pyttsx3 de basarisiz: %s", e2)

        time.sleep(self.mesaj_gecikmesi)

    def _gtts_ile_oku(self, mesaj):
        """Google TTS ile ses uretir ve calar."""
        from gtts import gTTS
        tts = gTTS(text=mesaj, lang="tr", slow=False)
        tts.save(self.ses_dosya)
        ses_dosya_cal(self.ses_dosya)

    def _pyttsx3_ile_oku(self, mesaj):
        """Edge TTS calismiyorsa pyttsx3 ile cevrimdisi oku."""
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        # Turkce ses varsa sec
        for v in voices:
            if "turkish" in v.name.lower() or "tr" in v.id.lower():
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", 150)
        engine.setProperty("volume", 1.0)
        engine.say(mesaj)
        engine.runAndWait()
        engine.stop()

        time.sleep(self.mesaj_gecikmesi)

    def _ses_uret_ve_cal(self, mesaj):
        """Edge TTS ile ses dosyası üretir ve çalar."""
        import asyncio
        import edge_tts

        # Python 3.8 uyumlu asyncio kullanımı
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _uret():
            communicate = edge_tts.Communicate(mesaj, self.ses, rate=self.ses_hizi)
            await communicate.save(self.ses_dosya)

        loop.run_until_complete(_uret())

        # Ses dosyasını çal (Windows 7 uyumlu)
        ses_dosya_cal(self.ses_dosya)

    def kapat(self):
        try:
            if os.path.exists(self.ses_dosya):
                os.remove(self.ses_dosya)
        except Exception:
            pass
        log.info("Baofeng TTS kapatildi.")


# ── Ana Döngü ────────────────────────────────────────────────────────────────


def ana_dongu(gonderici, kontrol_arasi, min_buyukluk, baofeng_modu=False):
    """Sürekli olarak AFAD'dan veri çeker ve yeni depremleri telsize gönderir."""

    son_tarih = None  # En son okunan depremin tarihi
    ilk_calisma = True
    mod_adi = "Baofeng Sesli" if baofeng_modu else "Seri Port"

    log.info("=" * 60)
    log.info("AFAD Deprem -> Telsiz Sistemi Baslatildi [%s]", mod_adi)
    log.info("Min buyukluk: %.1f | Kontrol araligi: %d sn",
             min_buyukluk, kontrol_arasi)
    log.info("Cikmak icin Ctrl+C")
    log.info("=" * 60)

    try:
        while True:
            try:
                depremler = deprem_verisi_cek(min_buyukluk)

                if not depremler:
                    log.warning("Deprem verisi alinamadi, tekrar denenecek...")
                    time.sleep(kontrol_arasi)
                    continue

                if ilk_calisma:
                    # Ilk calismada en son depremin tarihini kaydet ve oku
                    son = depremler[0]
                    son_tarih = _tarih_parse(son["tarih"])
                    log.info("Son deprem: M%.1f %s (%s)",
                             son["buyukluk"], son["yer"],
                             _tarih_saat_al(son["tarih"]))
                    if baofeng_modu:
                        mesaj = sesli_mesaj_olustur(son)
                    else:
                        mesaj = telsiz_mesaji_olustur(son)
                    gonderici.gonder(mesaj)
                    log.info(
                        "Ilk tarama tamamlandi. Baslangic tarihi: %s "
                        "Bundan sonra sadece yeni depremler izleniyor...",
                        _tarih_saat_al(son["tarih"]),
                    )
                    ilk_calisma = False
                else:
                    # Sadece son_tarih'ten sonraki depremleri oku
                    yeniler = []
                    for deprem in depremler:
                        d_tarih = _tarih_parse(deprem["tarih"])
                        if d_tarih and son_tarih and d_tarih > son_tarih:
                            yeniler.append(deprem)

                    if yeniler:
                        # En eskiden en yeniye oku
                        yeniler.reverse()
                        for deprem in yeniler:
                            if baofeng_modu:
                                mesaj = sesli_mesaj_olustur(deprem)
                            else:
                                mesaj = telsiz_mesaji_olustur(deprem)
                            log.info("YENI DEPREM TESPIT EDILDI!")
                            gonderici.gonder(mesaj)
                        # En son depremin tarihini guncelle
                        son_tarih = _tarih_parse(yeniler[-1]["tarih"])
                        log.info("%d yeni deprem telsize gonderildi.", len(yeniler))
                    else:
                        log.debug("Yeni deprem yok.")

            except Exception as e:
                log.error("Dongu hatasi: %s", e)

            time.sleep(kontrol_arasi)

    except KeyboardInterrupt:
        log.info("\nKullanici tarafindan durduruldu.")
    finally:
        gonderici.kapat()


# ── Tek Seferlik ─────────────────────────────────────────────────────────────


def tek_seferlik_cek(gonderici, min_buyukluk, adet, baofeng_modu=False):
    """Depremleri bir kez çeker, gösterir/seslendirir ve çıkar."""
    depremler = deprem_verisi_cek(min_buyukluk)

    if not depremler:
        log.error("Deprem verisi alinamadi!")
        return

    mod_adi = "Baofeng Sesli" if baofeng_modu else "Metin"
    print("\n" + "=" * 65)
    print(" AFAD Son Depremler (M >= {:.1f}) - Ilk {} kayit [{}]".format(
        min_buyukluk, adet, mod_adi))
    print("=" * 65)

    for deprem in depremler[:adet]:
        if baofeng_modu:
            mesaj = sesli_mesaj_olustur(deprem)
        else:
            mesaj = telsiz_mesaji_olustur(deprem)
        gonderici.gonder(mesaj)

    print("=" * 65)
    print(" Toplam: %d deprem bulundu.\n" % len(depremler))
    gonderici.kapat()


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="AFAD Son Depremler -> Telsiz Gonderici (Baofeng Destekli) [Win7]",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ornekler:
  python deprem_telsiz.py                             # Test modu, ekrana basar
  python deprem_telsiz.py --tek-sefer                  # Son depremleri bir kez goster
  python deprem_telsiz.py --baofeng                    # Baofeng sesli anons (VOX)
  python deprem_telsiz.py --baofeng --tek-sefer        # Sesli test (bir kez okur)
  python deprem_telsiz.py --baofeng --min 3.0          # Sadece M3.0+ seslendir
  python deprem_telsiz.py --port COM3                  # Seri port (dijital telsiz)
        """,
    )

    # Mod seçimi
    parser.add_argument(
        "--baofeng",
        action="store_true",
        help="Baofeng modu: Sesli anons uretir, VOX ile yayinlanir.",
    )
    parser.add_argument(
        "--port", "-p",
        default=None,
        help="Seri port (dijital telsiz). Belirtilmezse test modu.",
    )
    parser.add_argument(
        "--baud", "-b",
        type=int,
        default=VARSAYILAN_BAUD_RATE,
        help="Seri port baud rate (varsayilan: %d)" % VARSAYILAN_BAUD_RATE,
    )

    # Baofeng ses ayarları
    parser.add_argument(
        "--ses-tipi",
        default="erkek",
        choices=["erkek", "kadin"],
        help="Ses tipi: erkek veya kadin (varsayilan: erkek)",
    )
    parser.add_argument(
        "--ses-hizi",
        default="+0%",
        help="Konusma hizi (varsayilan: +0%%, yavas: -20%%, hizli: +20%%)",
    )

    # Genel ayarlar
    parser.add_argument(
        "--min", "-m",
        type=float,
        default=VARSAYILAN_MIN_BUYUKLUK,
        dest="min_buyukluk",
        help="Minimum deprem buyuklugu (varsayilan: %.1f)" % VARSAYILAN_MIN_BUYUKLUK,
    )
    parser.add_argument(
        "--aralik", "-a",
        type=int,
        default=VARSAYILAN_KONTROL_ARASI,
        help="Kontrol araligi saniye (varsayilan: %d)" % VARSAYILAN_KONTROL_ARASI,
    )
    parser.add_argument(
        "--tek-sefer", "-t",
        action="store_true",
        help="Depremleri bir kez cek, goster/seslendir ve cik",
    )
    parser.add_argument(
        "--adet", "-n",
        type=int,
        default=20,
        help="Tek seferlik modda gosterilecek deprem sayisi (varsayilan: 20)",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Debug loglari ac",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Gönderici oluştur
    if args.baofeng:
        gonderici = BaofengGonderici(
            ses_hizi=args.ses_hizi,
            ses_tipi=args.ses_tipi,
        )
    elif args.port:
        gonderici = TelsizGonderici(port=args.port, baud=args.baud)
    else:
        gonderici = TelsizGonderici(port=None)

    if args.tek_sefer:
        tek_seferlik_cek(gonderici, args.min_buyukluk, args.adet, args.baofeng)
    else:
        ana_dongu(gonderici, args.aralik, args.min_buyukluk, args.baofeng)


if __name__ == "__main__":
    main()
