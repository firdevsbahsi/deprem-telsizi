#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AFAD Son Depremler -> Telsiz Gönderici (Baofeng Destekli)
==========================================================
AFAD'dan son deprem verilerini çeker, yeni depremleri tespit eder
ve Baofeng telsiz üzerinden sesli olarak yayınlar.

Baofeng Modu (--baofeng):
  Deprem bilgisini Türkçe seslendirir, ses kartı çıkışından
  Baofeng'in mikrofon girişine kablo ile gönderir.
  Baofeng'de VOX aktif olmalı → ses gelince otomatik yayın yapar.

Kullanım:
  python deprem_telsiz.py                        # Test modu (ekrana basar)
  python deprem_telsiz.py --baofeng               # Baofeng TTS modu
  python deprem_telsiz.py --baofeng --tek-sefer    # Sesli test (bir kez okur)
  python deprem_telsiz.py --port COM3              # Seri port modu (dijital telsiz)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

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
    """Tarih stringini datetime objesine çevirir."""
    try:
        s = str(tarih_str).strip()
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        # "2026.04.20 14:29:09" (Kandilli formatı)
        if "." in s[:10] and len(s) >= 19:
            return datetime.strptime(s[:19], "%Y.%m.%d %H:%M:%S").replace(
                tzinfo=timezone(timedelta(hours=3))
            )
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone(timedelta(hours=3))
        )
    except Exception:
        return None


def deprem_verisi_cek(min_buyukluk: float = 0.0, limit: int = 100,
                     son_saat: int = 24) -> list[dict]:
    """AFAD + Kandilli'den deprem verisi çeker, birleştirir, tarihe göre sıralar.

    İki kaynağı da dener, sonuçları birleştirip en son tarihli olan başa gelecek
    şekilde sıralar. Böylece hiçbir deprem kaçırılmaz.
    """
    tum_depremler = []

    # 1) AFAD HTML
    afad = html_den_cek(min_buyukluk)
    if afad:
        log.info("AFAD: %d deprem", len(afad))
        tum_depremler.extend(afad)

    # 2) AFAD API (HTML başarısız olduysa)
    if not afad:
        log.info("AFAD HTML başarısız, API deneniyor...")
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

    # Tekrar edenleri kaldır (aynı saat + benzer konum = aynı deprem)
    tum_depremler = _tekrarlari_kaldir(tum_depremler)

    # Tarihe göre sırala (en yeni başta)
    tum_depremler = _tarihe_gore_sirala(tum_depremler)

    return _tarih_filtrele(tum_depremler, son_saat)


def _afad_api_cek(min_buyukluk: float, limit: int) -> list[dict]:
    """AFAD API'den deprem verisi çeker."""
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

    for api_url in [AFAD_API_URL, AFAD_API_URL_ALT]:
        try:
            resp = requests.get(api_url, params=params, timeout=15)
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
            log.warning("API hatası (%s): %s", api_url, e)
    return []


def kandilli_den_cek(min_buyukluk: float = 0.0) -> list[dict]:
    """Kandilli Rasathanesi'nden son depremleri çeker (KOERI lst0.asp)."""
    import re

    try:
        resp = requests.get(KANDILLI_URL, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        metin = resp.text
    except Exception as e:
        log.warning("Kandilli bağlantı hatası: %s", e)
        return []

    depremler = []
    # Kandilli formatı: 2026.04.20 14:29:09  39.2208   28.1163   11.4  -.- 1.3  -.-  YER
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

        # En büyük magnitude değerini al
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


def _tarihe_gore_sirala(depremler: list) -> list:
    """Depremleri tarihe göre sıralar (en yeni başta)."""
    def _sort_key(d):
        dt = _tarih_parse(d["tarih"])
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt

    return sorted(depremler, key=_sort_key, reverse=True)


def _tekrarlari_kaldir(depremler: list) -> list:
    """AFAD ve Kandilli'den gelen aynı depremleri teke düşürür.

    Aynı deprem = tarih farkı < 2 dakika + koordinat farkı < 0.1 derece.
    """
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


def _tarih_filtrele(depremler: list, son_saat: int) -> list:
    """Sadece son N saat içindeki depremleri filtreler."""
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


def html_den_cek(min_buyukluk: float = 0.0) -> list[dict]:
    """AFAD HTML sayfasından son depremleri parse eder."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.error("bs4 (BeautifulSoup) yüklü değil. pip install beautifulsoup4")
        return []

    try:
        resp = requests.get(AFAD_HTML_URL, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        depremler = []
        tablo = soup.find("table")
        if not tablo:
            log.error("HTML'de tablo bulunamadı.")
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

        log.info("HTML'den %d deprem çekildi.", len(depremler))
        return depremler

    except Exception as e:
        log.error("HTML çekme hatası: %s", e)
        return []


# ── Mesaj Formatlama ─────────────────────────────────────────────────────────


def _tarih_saat_al(tarih_str) -> str:
    """Tarih stringinden saat:dakika çıkarır."""
    try:
        if "T" in str(tarih_str):
            dt = datetime.fromisoformat(str(tarih_str).replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(str(tarih_str)[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M")
    except Exception:
        return str(tarih_str)[-8:-3] if len(str(tarih_str)) > 8 else str(tarih_str)


def _tarih_gun_al(tarih_str) -> str:
    """Tarih stringinden gün.ay çıkarır (ör: 20.04)."""
    try:
        if "T" in str(tarih_str):
            dt = datetime.fromisoformat(str(tarih_str).replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(str(tarih_str)[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d.%m")
    except Exception:
        return ""


def telsiz_mesaji_olustur(deprem: dict) -> str:
    """Deprem verisini telsiz metin formatına çevirir.

    Örnek: DEPREM! M3.2 | 20.04 11:58 | Onikisubat (Kahramanmaras) | Derin:6.99km | 37.86/36.47
    """
    saat = _tarih_saat_al(deprem["tarih"])
    gun = _tarih_gun_al(deprem["tarih"])
    yer = turkce_ascii(deprem["yer"])

    return (
        f"DEPREM! M{deprem['buyukluk']:.1f} | "
        f"{gun} {saat} | {yer} | "
        f"Derin:{deprem['derinlik']}km | "
        f"{deprem['enlem']}/{deprem['boylam']}"
    )


def sesli_mesaj_olustur(deprem: dict) -> str:
    """Deprem verisini Türkçe sesli anons formatına çevirir.

    Örnek: 'Afet ve Acil Durum Başkanlığı verilerine göre saat 19:30
     sularında Kütahya ve çevresinde 3.4 büyüklüğünde yer sarsıntısı
     meydana gelmiştir.'
    """
    saat = _tarih_saat_al(deprem["tarih"])
    buyukluk = deprem["buyukluk"]
    yer = deprem["yer"]
    kaynak = deprem.get("kaynak", "AFAD")

    if kaynak == "Kandilli":
        kurum = "Kandilli Rasathanesi verilerine göre"
    else:
        kurum = "Afet ve Acil Durum Başkanlığı verilerine göre"

    return (
        f"{kurum} "
        f"saat {saat} sularında "
        f"{yer} ve çevresinde "
        f"{buyukluk:.1f} büyüklüğünde yer sarsıntısı meydana gelmiştir."
    )


def turkce_ascii(metin: str) -> str:
    """Türkçe karakterleri ASCII karşılıklarına çevirir."""
    tr_map = str.maketrans("çÇğĞıİöÖşŞüÜ", "cCgGiIoOsSuU")
    return metin.translate(tr_map)


# ── Gönderici Sınıfları ──────────────────────────────────────────────────────


class TelsizGonderici:
    """Seri port üzerinden telsize mesaj gönderir (dijital telsizler için)."""

    def __init__(self, port=None, baud=VARSAYILAN_BAUD_RATE,
                 mesaj_gecikmesi=VARSAYILAN_MESAJ_GECIKMESI):
        self.port = port
        self.baud = baud
        self.mesaj_gecikmesi = mesaj_gecikmesi
        self.ser = None
        self.test_modu = port is None

        if self.test_modu:
            log.info("TEST MODU: Seri port belirtilmedi, mesajlar ekrana basılacak.")
        else:
            if not SERIAL_AVAILABLE:
                log.error("pyserial yüklü değil! pip install pyserial")
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
                log.info("Seri port açıldı: %s @ %d baud", port, baud)
            except serial.SerialException as e:
                log.error("Seri port açılamadı: %s", e)
                sys.exit(1)

    def gonder(self, mesaj):
        if self.test_modu:
            print(f"  📡 {mesaj}")
        else:
            veri = (mesaj + "\r\n").encode("ascii", errors="replace")
            self.ser.write(veri)
            self.ser.flush()
            log.info("Gönderildi (%d byte): %s", len(veri), mesaj[:60])
        time.sleep(self.mesaj_gecikmesi)

    def kapat(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            log.info("Seri port kapatıldı.")


class BaofengGonderici:
    """Baofeng telsiz için doğal sesli anons gönderici (Edge TTS).

    Microsoft Edge TTS ile doğal Türkçe ses üretir.
    Ses dosyasını oluşturur ve çalar.
    """

    # Türkçe ses seçenekleri (doğal sesler)
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
        self.ses_dosya = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_anons.mp3")

        log.info("BAOFENG MODU: Doğal Türkçe ses aktif (ses=%s, hız=%s)", self.ses, ses_hizi)
        if not test_modu:
            log.info("Baofeng'de VOX'un açık olduğundan emin olun!")

    def gonder(self, mesaj):
        """Metni doğal Türkçe sesle okur."""
        import asyncio

        print(f"  🔊 {mesaj}")
        log.info("Seslendiriliyor: %s", mesaj[:80])

        if not self.test_modu:
            try:
                asyncio.run(self._ses_uret_ve_cal(mesaj))
            except Exception as e:
                log.error("Ses üretme hatası: %s", e)

        time.sleep(self.mesaj_gecikmesi)

    async def _ses_uret_ve_cal(self, mesaj):
        """Edge TTS ile ses dosyası üretir ve çalar."""
        import edge_tts

        communicate = edge_tts.Communicate(mesaj, self.ses, rate=self.ses_hizi)
        await communicate.save(self.ses_dosya)

        # Ses dosyasını çal
        if sys.platform == "win32":
            import subprocess
            subprocess.run(
                ["powershell", "-c",
                 f'Add-Type -AssemblyName PresentationCore; '
                 f'$p = New-Object System.Windows.Media.MediaPlayer; '
                 f'$p.Open("{os.path.abspath(self.ses_dosya)}"); '
                 f'Start-Sleep -Milliseconds 500; $p.Play(); '
                 f'while($p.NaturalDuration.HasTimeSpan -eq $false){{Start-Sleep -Milliseconds 100}}; '
                 f'Start-Sleep -Seconds $p.NaturalDuration.TimeSpan.TotalSeconds; '
                 f'$p.Close()'],
                capture_output=True,
            )
        else:
            os.system(f'mpg123 -q "{self.ses_dosya}" 2>/dev/null || '
                      f'ffplay -nodisp -autoexit -loglevel quiet "{self.ses_dosya}"')

    def kapat(self):
        # Geçici ses dosyasını temizle
        try:
            if os.path.exists(self.ses_dosya):
                os.remove(self.ses_dosya)
        except Exception:
            pass
        log.info("Baofeng TTS kapatıldı.")


# ── Ana Döngü ────────────────────────────────────────────────────────────────


def ana_dongu(gonderici, kontrol_arasi, min_buyukluk, baofeng_modu=False):
    """Sürekli olarak AFAD'dan veri çeker ve yeni depremleri telsize gönderir."""

    # Başlangıç zamanı hemen şimdi ayarlanır; döngüye girmeden önce.
    tr_saat = timezone(timedelta(hours=3))
    son_tarih = datetime.now(tz=tr_saat)
    mod_adi = "Baofeng Sesli" if baofeng_modu else "Seri Port"

    log.info("=" * 60)
    log.info("AFAD Deprem -> Telsiz Sistemi Başlatıldı [%s]", mod_adi)
    log.info("Min büyüklük: %.1f | Kontrol aralığı: %d sn", min_buyukluk, kontrol_arasi)
    log.info("Başlangıç saati: %s — sadece bu saatten sonraki depremler duyurulacak.", son_tarih.strftime("%H:%M:%S"))
    log.info("Çıkmak için Ctrl+C")
    log.info("=" * 60)

    try:
        while True:
            try:
                depremler = deprem_verisi_cek(min_buyukluk)

                if not depremler:
                    log.info("Son 24 saatte M>=%.1f deprem bulunamadı, %d sn sonra tekrar kontrol edilecek...",
                             min_buyukluk, kontrol_arasi)
                    time.sleep(kontrol_arasi)
                    continue

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
                        log.info("YENİ DEPREM TESPİT EDİLDİ!")
                        gonderici.gonder(mesaj)
                    # En son depremin tarihini güncelle
                    son_tarih = _tarih_parse(yeniler[-1]["tarih"])
                    log.info("%d yeni deprem telsize gönderildi.", len(yeniler))
                else:
                    log.debug("Yeni deprem yok.")

            except Exception as e:
                log.error("Döngü hatası: %s", e)

            time.sleep(kontrol_arasi)

    except KeyboardInterrupt:
        log.info("\nKullanıcı tarafından durduruldu.")
    finally:
        gonderici.kapat()


# ── Tek Seferlik ─────────────────────────────────────────────────────────────


def tek_seferlik_cek(gonderici, min_buyukluk, adet, baofeng_modu=False):
    """Depremleri bir kez çeker, gösterir/seslendirir ve çıkar."""
    depremler = deprem_verisi_cek(min_buyukluk)

    if not depremler:
        log.error("Deprem verisi alınamadı!")
        return

    mod_adi = "Baofeng Sesli" if baofeng_modu else "Metin"
    print(f"\n{'='*65}")
    print(f" AFAD Son Depremler (M >= {min_buyukluk:.1f}) — İlk {adet} kayıt [{mod_adi}]")
    print(f"{'='*65}")

    for deprem in depremler[:adet]:
        if baofeng_modu:
            mesaj = sesli_mesaj_olustur(deprem)
        else:
            mesaj = telsiz_mesaji_olustur(deprem)
        gonderici.gonder(mesaj)

    print(f"{'='*65}")
    print(f" Toplam: {len(depremler)} deprem bulundu.\n")
    gonderici.kapat()


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="AFAD Son Depremler → Telsiz Gönderici (Baofeng Destekli)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python deprem_telsiz.py                             # Test modu, ekrana basar
  python deprem_telsiz.py --tek-sefer                  # Son depremleri bir kez göster
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
        help="Baofeng modu: Sesli anons üretir, VOX ile yayınlanır.",
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
        help=f"Seri port baud rate (varsayılan: {VARSAYILAN_BAUD_RATE})",
    )

    # Baofeng ses ayarları
    parser.add_argument(
        "--ses-tipi",
        default="erkek",
        choices=["erkek", "kadin"],
        help="Ses tipi: erkek veya kadin (varsayılan: erkek)",
    )
    parser.add_argument(
        "--ses-hizi",
        default="+0%",
        help="Konuşma hızı (varsayılan: +0%%, yavaş: -20%%, hızlı: +20%%)",
    )

    # Genel ayarlar
    parser.add_argument(
        "--min", "-m",
        type=float,
        default=VARSAYILAN_MIN_BUYUKLUK,
        dest="min_buyukluk",
        help=f"Minimum deprem büyüklüğü (varsayılan: {VARSAYILAN_MIN_BUYUKLUK})",
    )
    parser.add_argument(
        "--aralik", "-a",
        type=int,
        default=VARSAYILAN_KONTROL_ARASI,
        help=f"Kontrol aralığı saniye (varsayılan: {VARSAYILAN_KONTROL_ARASI})",
    )
    parser.add_argument(
        "--tek-sefer", "-t",
        action="store_true",
        help="Depremleri bir kez çek, göster/seslendir ve çık",
    )
    parser.add_argument(
        "--adet", "-n",
        type=int,
        default=20,
        help="Tek seferlik modda gösterilecek deprem sayısı (varsayılan: 20)",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Debug logları aç",
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
