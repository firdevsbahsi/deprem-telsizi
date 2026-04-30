#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MGM Sarı Kod Meteorolojik Uyarı -> Telsiz Seslendirici
========================================================
** Windows 7 Uyumlu Sürüm (Python 3.8) **

Meteoroloji Genel Müdürlüğü API'sinden meteorolojik uyarıları çeker,
saat 10:00, 12:00, 14:00, 16:00'da Edge TTS ile seslendirir.
Baofeng telsizde VOX aktif iken otomatik yayın yapar.

Kullanım:
  python sari_uyari.py                 # Zamanlayıcı modu (10, 12, 14, 16)
  python sari_uyari.py --tek-sefer     # Bir kez çek ve seslendir
  python sari_uyari.py --tek-sefer --sessiz   # Sadece ekrana yaz
"""

from __future__ import annotations

import asyncio
import argparse
import logging
import os
import ssl
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


# ── SSL Fix (Windows 7 sertifika sorunu) ────────────────────────────────────

class Win7SSLAdapter(HTTPAdapter):
    """Windows 7 için SSL uyumluluk adaptörü."""
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.load_verify_locations(certifi.where())
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sari_uyari")

MGM_API_URL = "https://servis.mgm.gov.tr/web/meteoalarm"

ANONS_SAATLERI = [10, 12, 14, 16]

SESLER = {
    "erkek": "tr-TR-AhmetNeural",
    "kadin": "tr-TR-EmelNeural",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/109.0.0.0 Safari/537.36"
    ),
    "Origin": "https://www.mgm.gov.tr",
    "Referer": "https://www.mgm.gov.tr/meteouyari/turkiye.aspx",
}

TR_SAAT = timezone(timedelta(hours=3))

# ── İl Bilgileri (merkezId -> il adı) ────────────────────────────────────────

IL_BILGILERI = {
    90101: "Adana", 90201: "Adiyaman", 90301: "Afyonkarahisar", 90401: "Agri",
    90501: "Amasya", 90601: "Ankara", 90701: "Antalya", 90801: "Artvin",
    90901: "Aydin", 91001: "Balikesir", 91101: "Bilecik", 91201: "Bingol",
    91301: "Bitlis", 91401: "Bolu", 91501: "Burdur", 91601: "Bursa",
    91701: "Canakkale", 91801: "Cankiri", 91901: "Corum", 92001: "Denizli",
    92101: "Diyarbakir", 92201: "Edirne", 92301: "Elazig", 92401: "Erzincan",
    92501: "Erzurum", 92601: "Eskisehir", 92701: "Gaziantep", 92801: "Giresun",
    92901: "Gumushane", 93001: "Hakkari", 93101: "Hatay", 93201: "Isparta",
    93301: "Mersin", 93401: "Istanbul", 93501: "Izmir", 93601: "Kars",
    93701: "Kastamonu", 93801: "Kayseri", 93901: "Kirklareli", 94001: "Kirsehir",
    94101: "Kocaeli", 94201: "Konya", 94301: "Kutahya", 94401: "Malatya",
    94501: "Manisa", 94601: "Kahramanmaras", 94701: "Mardin", 94801: "Mugla",
    94901: "Mus", 95001: "Nevsehir", 95101: "Nigde", 95201: "Ordu",
    95301: "Rize", 95401: "Sakarya", 95501: "Samsun", 95601: "Siirt",
    95701: "Sinop", 95801: "Sivas", 95901: "Tekirdag", 96001: "Tokat",
    96101: "Trabzon", 96201: "Tunceli", 96301: "Sanliurfa", 96401: "Usak",
    96501: "Van", 96601: "Yozgat", 96701: "Zonguldak", 96801: "Aksaray",
    96901: "Bayburt", 97001: "Karaman", 97101: "Kirikkale", 97201: "Batman",
    97301: "Sirnak", 97401: "Bartin", 97501: "Ardahan", 97601: "Igdir",
    97701: "Yalova", 97801: "Karabuk", 97901: "Kilis", 98001: "Osmaniye",
    98101: "Duzce",
}

# Hava olayı Türkçe isimleri
HADISE_ISIMLERI = {
    "thunderstorm": "gok gurultulu saganak",
    "rain": "yagmur",
    "snow": "kar yagisi",
    "wind": "kuvvetli ruzgar",
    "fog": "sis",
    "ice": "buzlanma",
    "cold": "soguk hava",
    "hot": "sicak hava",
    "dust": "toz tasinimi",
    "avalanche": "cig",
    "snowmelt": "kar erimesi",
    "agricultural": "zirai don",
}


def ilce_id_to_il(ilce_id):
    """Ilce ID'sinden il adini dondurur."""
    il_merkez_id = int(str(ilce_id)[:3] + "01")
    return IL_BILGILERI.get(il_merkez_id, "Bilinmeyen (%s)" % ilce_id)


# ── Ses Çalma (Windows 7 Uyumlu) ────────────────────────────────────────────


def ses_dosya_cal(dosya_yolu):
    """MP3 dosyasını Windows 7 uyumlu şekilde çalar."""
    dosya_yolu = os.path.abspath(dosya_yolu)

    # Yöntem 1: PowerShell MediaPlayer
    try:
        ps_script = (
            '[System.Reflection.Assembly]::LoadWithPartialName("PresentationCore") | Out-Null; '
            '$p = New-Object System.Windows.Media.MediaPlayer; '
            '$p.Open([Uri]::new("%s")); ' % dosya_yolu +
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

    # Yöntem 2: Windows Media Player
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

    # Yöntem 3: start komutu
    try:
        os.startfile(dosya_yolu)
        time.sleep(15)
    except Exception as e:
        log.error("Ses calma tamamen basarisiz: %s", e)


# ── MGM API'den Uyarı Çekme ─────────────────────────────────────────────────


def uyarilari_cek(gun="today"):
    """MGM API'den meteorolojik uyarıları çeker."""
    url = "%s/%s" % (MGM_API_URL, gun)
    try:
        session = guvenli_session()
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        api_veri = resp.json()
    except Exception as e:
        log.error("MGM API hatasi: %s", e)
        return []

    if not api_veri:
        log.info("API'den uyari verisi gelmedi.")
        return []

    uyarilar = []

    for alarm in api_veri:
        text = alarm.get("text", {})
        weather = alarm.get("weather", {})
        towns = alarm.get("towns", {})
        begin = alarm.get("begin", "")
        end = alarm.get("end", "")

        baslangic = _tarih_formatla(begin)
        bitis = _tarih_formatla(end)

        for renk in ["yellow", "orange", "red"]:
            uyari_metni = text.get(renk, "")
            hadiseler = weather.get(renk, [])
            ilceler = towns.get(renk, [])

            if not uyari_metni or not ilceler:
                continue

            # Ilceleri illere gore grupla
            il_gruplari = {}
            for ilce_id in ilceler:
                il_adi = ilce_id_to_il(ilce_id)
                if il_adi not in il_gruplari:
                    il_gruplari[il_adi] = []
                il_gruplari[il_adi].append(ilce_id)

            renk_tr = {"yellow": "sari", "orange": "turuncu", "red": "kirmizi"}

            uyarilar.append({
                "renk": renk_tr.get(renk, renk),
                "metin": uyari_metni.replace("\n", " ").strip(),
                "hadiseler": hadiseler,
                "iller": list(il_gruplari.keys()),
                "baslangic": baslangic,
                "bitis": bitis,
            })

    log.info("API'den %d uyari cekildi.", len(uyarilar))
    return uyarilar


def _tarih_formatla(iso_str):
    """ISO tarih stringini Turkce formata cevirir."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_tr = dt.astimezone(TR_SAAT)

        aylar = {
            1: "Ocak", 2: "Subat", 3: "Mart", 4: "Nisan",
            5: "Mayis", 6: "Haziran", 7: "Temmuz", 8: "Agustos",
            9: "Eylul", 10: "Ekim", 11: "Kasim", 12: "Aralik",
        }
        ay = aylar.get(dt_tr.month, "")
        return "%d %s %d saat %s" % (dt_tr.day, ay, dt_tr.year, dt_tr.strftime("%H:%M"))
    except Exception:
        return iso_str


# ── Anons Metni Oluşturma ───────────────────────────────────────────────────


def anons_metni_olustur(uyarilar, sadece_sari=False):
    """Uyari listesinden sesli anons metni olusturur."""
    if not uyarilar:
        return None

    if sadece_sari:
        uyarilar = [u for u in uyarilar if u["renk"] == "sari"]
        if not uyarilar:
            return None

    tum_iller = []
    tum_hadiseler = set()
    tum_riskler = set()
    for u in uyarilar:
        for il in u["iller"]:
            if il not in tum_iller:
                tum_iller.append(il)
        for h in u["hadiseler"]:
            tum_hadiseler.add(HADISE_ISIMLERI.get(h, h))
        metin_lower = u["metin"].lower()
        for risk in ["sel", "su baskini", "dolu", "firtina", "hortum", "buzlanma", "cig"]:
            if risk in metin_lower:
                tum_riskler.add(risk)

    iller_str = ", ".join(tum_iller)
    hadise_str = ", ".join(tum_hadiseler)
    risk_str = ", ".join(tum_riskler) if tum_riskler else ""

    renk_label = "Sari kod"
    for u in uyarilar:
        if u["renk"] == "kirmizi":
            renk_label = "Kirmizi kod"
            break
        if u["renk"] == "turuncu":
            renk_label = "Turuncu kod"

    metin = "%s uyarisi. %s. Kuvvetli %s" % (renk_label, iller_str, hadise_str)
    if risk_str:
        metin += ", %s riski" % risk_str
    metin += ". Dikkatli olun."

    return metin


# ── TTS ve Ses Çalma ────────────────────────────────────────────────────────


def _ses_uret_sync(mesaj, ses_dosya, ses, hiz):
    """Edge TTS ile ses dosyasi uretir (Python 3.8 uyumlu)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _uret():
        communicate = edge_tts.Communicate(mesaj, ses, rate=hiz)
        await communicate.save(ses_dosya)

    loop.run_until_complete(_uret())


# ── Anons Fonksiyonu ────────────────────────────────────────────────────────


def anons_yap(ses="tr-TR-AhmetNeural", hiz="-10%", sadece_sari=False):
    """Uyarilari ceker, seslendirir ve telsizden yayinlar."""
    log.info("=" * 60)
    log.info("Meteorolojik uyarilar cekiliyor...")

    uyarilar = uyarilari_cek("today")

    if not uyarilar:
        log.info("Aktif meteorolojik uyari bulunamadi.")
        return

    sari = sum(1 for u in uyarilar if u["renk"] == "sari")
    turuncu = sum(1 for u in uyarilar if u["renk"] == "turuncu")
    kirmizi = sum(1 for u in uyarilar if u["renk"] == "kirmizi")
    log.info("Uyarilar: %d sari, %d turuncu, %d kirmizi", sari, turuncu, kirmizi)

    metin = anons_metni_olustur(uyarilar, sadece_sari=sadece_sari)
    if not metin:
        log.info("Filtreye uyan uyari bulunamadi.")
        return

    print("\n" + "=" * 65)
    print("  ANONS METNI:")
    print("=" * 65)
    print(metin)
    print("=" * 65 + "\n")

    ses_dosya = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_uyari_anons.mp3"
    )

    if TTS_AVAILABLE:
        try:
            log.info("Ses dosyasi olusturuluyor (Edge TTS)...")
            _ses_uret_sync(metin, ses_dosya, ses, hiz)
            log.info("Ses caliniyor (Baofeng VOX ile yayin)...")
            ses_dosya_cal(ses_dosya)
            log.info("Anons tamamlandi.")
        except Exception as e:
            log.error("TTS hatasi: %s", e)
        finally:
            try:
                if os.path.exists(ses_dosya):
                    os.remove(ses_dosya)
            except OSError:
                pass
    else:
        log.warning("edge-tts yuklu degil veya --sessiz modu aktif.")


# ── Zamanlayıcı ──────────────────────────────────────────────────────────────


def zamanlayici(ses, hiz, sadece_sari=False):
    """Belirtilen saatlerde anons yapar."""
    log.info("=" * 60)
    log.info("MGM Meteorolojik Uyari Telsiz Sistemi")
    log.info("Anons saatleri: %s", ", ".join("%02d:00" % s for s in ANONS_SAATLERI))
    log.info("Ses: %s | Hiz: %s", ses, hiz)
    log.info("Sadece sari: %s", "Evet" if sadece_sari else "Hayir (tumu)")
    log.info("Baofeng'de VOX'un acik oldugundan emin olun!")
    log.info("Cikmak icin Ctrl+C")
    log.info("=" * 60)

    yapilan = set()

    try:
        while True:
            simdi = datetime.now(tz=TR_SAAT)
            bugun = simdi.strftime("%Y-%m-%d")
            saat = simdi.hour
            dakika = simdi.minute

            if saat in ANONS_SAATLERI and dakika < 5:
                anahtar = "%s-%d" % (bugun, saat)
                if anahtar not in yapilan:
                    yapilan.add(anahtar)
                    log.info("Anons zamani: %02d:00", saat)
                    anons_yap(ses=ses, hiz=hiz, sadece_sari=sadece_sari)

            # Gece yarisi temizlik
            if saat == 0 and dakika == 0:
                yapilan.clear()

            time.sleep(30)

    except KeyboardInterrupt:
        log.info("\nKullanici tarafindan durduruldu.")


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="MGM Meteorolojik Uyari -> Telsiz Seslendirici [Win7]",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ornekler:
  python sari_uyari.py                          # Zamanlayici (10, 12, 14, 16)
  python sari_uyari.py --tek-sefer              # Bir kez seslendir
  python sari_uyari.py --tek-sefer --sessiz     # Sadece ekrana yaz
  python sari_uyari.py --ses-tipi kadin         # Kadin sesi ile
  python sari_uyari.py --sadece-sari            # Sadece sari uyarilar
        """,
    )
    parser.add_argument(
        "--tek-sefer", "-t",
        action="store_true",
        help="Uyarilari bir kez cek, seslendir ve cik.",
    )
    parser.add_argument(
        "--sessiz", "-s",
        action="store_true",
        help="Ses calmadan sadece ekrana yaz.",
    )
    parser.add_argument(
        "--sadece-sari",
        action="store_true",
        help="Sadece sari uyarilari seslendir (turuncu/kirmizi dahil etme).",
    )
    parser.add_argument(
        "--ses-tipi",
        default="erkek",
        choices=["erkek", "kadin"],
        help="Ses tipi (varsayilan: erkek)",
    )
    parser.add_argument(
        "--ses-hizi",
        default="-10%",
        help="Konusma hizi (varsayilan: -10%%, yavas: -20%%, hizli: +10%%)",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Debug loglari ac",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    ses = SESLER.get(args.ses_tipi, SESLER["erkek"])
    hiz = args.ses_hizi

    if args.sessiz:
        global TTS_AVAILABLE
        TTS_AVAILABLE = False

    if args.tek_sefer:
        anons_yap(ses=ses, hiz=hiz, sadece_sari=args.sadece_sari)
    else:
        zamanlayici(ses=ses, hiz=hiz, sadece_sari=args.sadece_sari)


if __name__ == "__main__":
    main()
