#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MGM Sarı Kod Meteorolojik Uyarı -> Telsiz Seslendirici
========================================================
Meteoroloji Genel Müdürlüğü API'sinden meteorolojik uyarıları çeker,
saat 10:00, 12:00, 14:00, 16:00'da Edge TTS ile seslendirir.
Baofeng telsizde VOX aktif iken otomatik yayın yapar.

Kullanım:
  python sari_uyari.py                 # Zamanlayıcı modu (10, 12, 14, 16)
  python sari_uyari.py --tek-sefer     # Bir kez çek ve seslendir
  python sari_uyari.py --tek-sefer --sessiz   # Sadece ekrana yaz
"""

import asyncio
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Origin": "https://www.mgm.gov.tr",
    "Referer": "https://www.mgm.gov.tr/meteouyari/turkiye.aspx",
}

TR_SAAT = timezone(timedelta(hours=3))

# ── İl Bilgileri (merkezId -> il adı) ────────────────────────────────────────

IL_BILGILERI = {
    90101: "Adana", 90201: "Adıyaman", 90301: "Afyonkarahisar", 90401: "Ağrı",
    90501: "Amasya", 90601: "Ankara", 90701: "Antalya", 90801: "Artvin",
    90901: "Aydın", 91001: "Balıkesir", 91101: "Bilecik", 91201: "Bingöl",
    91301: "Bitlis", 91401: "Bolu", 91501: "Burdur", 91601: "Bursa",
    91701: "Çanakkale", 91801: "Çankırı", 91901: "Çorum", 92001: "Denizli",
    92101: "Diyarbakır", 92201: "Edirne", 92301: "Elazığ", 92401: "Erzincan",
    92501: "Erzurum", 92601: "Eskişehir", 92701: "Gaziantep", 92801: "Giresun",
    92901: "Gümüşhane", 93001: "Hakkari", 93101: "Hatay", 93201: "Isparta",
    93301: "Mersin", 93401: "İstanbul", 93501: "İzmir", 93601: "Kars",
    93701: "Kastamonu", 93801: "Kayseri", 93901: "Kırklareli", 94001: "Kırşehir",
    94101: "Kocaeli", 94201: "Konya", 94301: "Kütahya", 94401: "Malatya",
    94501: "Manisa", 94601: "Kahramanmaraş", 94701: "Mardin", 94801: "Muğla",
    94901: "Muş", 95001: "Nevşehir", 95101: "Niğde", 95201: "Ordu",
    95301: "Rize", 95401: "Sakarya", 95501: "Samsun", 95601: "Siirt",
    95701: "Sinop", 95801: "Sivas", 95901: "Tekirdağ", 96001: "Tokat",
    96101: "Trabzon", 96201: "Tunceli", 96301: "Şanlıurfa", 96401: "Uşak",
    96501: "Van", 96601: "Yozgat", 96701: "Zonguldak", 96801: "Aksaray",
    96901: "Bayburt", 97001: "Karaman", 97101: "Kırıkkale", 97201: "Batman",
    97301: "Şırnak", 97401: "Bartın", 97501: "Ardahan", 97601: "Iğdır",
    97701: "Yalova", 97801: "Karabük", 97901: "Kilis", 98001: "Osmaniye",
    98101: "Düzce",
}

# Hava olayı Türkçe isimleri
HADISE_ISIMLERI = {
    "thunderstorm": "gök gürültülü sağanak",
    "rain": "yağmur",
    "snow": "kar yağışı",
    "wind": "kuvvetli rüzgar",
    "fog": "sis",
    "ice": "buzlanma",
    "cold": "soğuk hava",
    "hot": "sıcak hava",
    "dust": "toz taşınımı",
    "avalanche": "çığ",
    "snowmelt": "kar erimesi",
    "agricultural": "zirai don",
}


def ilce_id_to_il(ilce_id):
    """İlçe ID'sinden il adını döndürür. Örn: 92703 -> Gaziantep"""
    il_merkez_id = int(str(ilce_id)[:3] + "01")
    return IL_BILGILERI.get(il_merkez_id, f"Bilinmeyen ({ilce_id})")


# ── MGM API'den Uyarı Çekme ─────────────────────────────────────────────────


def uyarilari_cek(gun="today"):
    """MGM API'den meteorolojik uyarıları çeker.

    Args:
        gun: 'today' veya 'tomorrow'

    Returns:
        İşlenmiş uyarı listesi
    """
    url = f"{MGM_API_URL}/{gun}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        api_veri = resp.json()
    except Exception as e:
        log.error("MGM API hatası: %s", e)
        return []

    if not api_veri:
        log.info("API'den uyarı verisi gelmedi.")
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

            # İlçeleri illere göre grupla
            il_gruplari = {}
            for ilce_id in ilceler:
                il_adi = ilce_id_to_il(ilce_id)
                if il_adi not in il_gruplari:
                    il_gruplari[il_adi] = []
                il_gruplari[il_adi].append(ilce_id)

            renk_tr = {"yellow": "sarı", "orange": "turuncu", "red": "kırmızı"}

            uyarilar.append({
                "renk": renk_tr.get(renk, renk),
                "metin": uyari_metni.replace("\n", " ").strip(),
                "hadiseler": hadiseler,
                "iller": list(il_gruplari.keys()),
                "baslangic": baslangic,
                "bitis": bitis,
            })

    log.info("API'den %d uyarı çekildi.", len(uyarilar))
    return uyarilar


def _tarih_formatla(iso_str):
    """ISO tarih stringini Türkçe formata çevirir."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_tr = dt.astimezone(TR_SAAT)

        aylar = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
            5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
            9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
        }
        ay = aylar.get(dt_tr.month, "")
        return f"{dt_tr.day} {ay} {dt_tr.year} saat {dt_tr.strftime('%H:%M')}"
    except Exception:
        return iso_str


# ── Anons Metni Oluşturma ───────────────────────────────────────────────────

TURKCE_AYLAR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
    5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
    9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}


def anons_metni_olustur(uyarilar, sadece_sari=False):
    """Uyarı listesinden sesli anons metni oluşturur."""
    if not uyarilar:
        return None

    if sadece_sari:
        uyarilar = [u for u in uyarilar if u["renk"] == "sarı"]
        if not uyarilar:
            return None

    # Tüm ileri topla (tekrarsız, sıralı)
    tum_iller = []
    tum_hadiseler = set()
    tum_riskler = set()
    for u in uyarilar:
        for il in u["iller"]:
            if il not in tum_iller:
                tum_iller.append(il)
        for h in u["hadiseler"]:
            tum_hadiseler.add(HADISE_ISIMLERI.get(h, h))
        # Metin içinden riskleri çıkar
        metin_lower = u["metin"].lower()
        for risk in ["sel", "su baskını", "dolu", "fırtına", "hortum", "buzlanma", "çığ"]:
            if risk in metin_lower:
                tum_riskler.add(risk)

    iller_str = ", ".join(tum_iller)
    hadise_str = ", ".join(tum_hadiseler)
    risk_str = ", ".join(tum_riskler) if tum_riskler else ""

    renk_label = "Sarı kod"
    for u in uyarilar:
        if u["renk"] == "kırmızı":
            renk_label = "Kırmızı kod"
            break
        if u["renk"] == "turuncu":
            renk_label = "Turuncu kod"

    metin = f"{renk_label} uyarısı. {iller_str}. Kuvvetli {hadise_str}"
    if risk_str:
        metin += f", {risk_str} riski"
    metin += ". Dikkatli olun."

    return metin


# ── TTS ve Ses Çalma ────────────────────────────────────────────────────────


async def _ses_uret(mesaj, ses_dosya, ses, hiz):
    """Edge TTS ile ses dosyası üretir."""
    communicate = edge_tts.Communicate(mesaj, ses, rate=hiz)
    await communicate.save(ses_dosya)


def ses_cal(ses_dosya):
    """Ses dosyasını çalar (Windows - ses kartı çıkışından Baofeng'e)."""
    import subprocess
    dosya_yolu = os.path.abspath(ses_dosya)

    # PowerShell ile STA thread'de MediaPlayer kullan
    ps_script = (
        '[System.Reflection.Assembly]::LoadWithPartialName("PresentationCore") | Out-Null; '
        '$p = New-Object System.Windows.Media.MediaPlayer; '
        f'$p.Open([Uri]::new("{dosya_yolu}")); '
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
    try:
        subprocess.run(
            ["powershell", "-sta", "-NoProfile", "-c", ps_script],
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        log.warning("Ses çalma zaman aşımına uğradı.")
    except Exception as e:
        log.error("Ses çalma hatası: %s", e)


# ── Anons Fonksiyonu ────────────────────────────────────────────────────────


def anons_yap(ses="tr-TR-AhmetNeural", hiz="-10%", sadece_sari=False):
    """Uyarıları çeker, seslendirir ve telsizden yayınlar."""
    log.info("=" * 60)
    log.info("Meteorolojik uyarılar çekiliyor...")

    uyarilar = uyarilari_cek("today")

    if not uyarilar:
        log.info("Aktif meteorolojik uyarı bulunamadı.")
        return

    sari = sum(1 for u in uyarilar if u["renk"] == "sarı")
    turuncu = sum(1 for u in uyarilar if u["renk"] == "turuncu")
    kirmizi = sum(1 for u in uyarilar if u["renk"] == "kırmızı")
    log.info("Uyarılar: %d sarı, %d turuncu, %d kırmızı", sari, turuncu, kirmizi)

    metin = anons_metni_olustur(uyarilar, sadece_sari=sadece_sari)
    if not metin:
        log.info("Filtreye uyan uyarı bulunamadı.")
        return

    print(f"\n{'='*65}")
    print("  ANONS METNİ:")
    print(f"{'='*65}")
    print(metin)
    print(f"{'='*65}\n")

    ses_dosya = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_uyari_anons.mp3"
    )

    if TTS_AVAILABLE:
        try:
            log.info("Ses dosyası oluşturuluyor (Edge TTS)...")
            asyncio.run(_ses_uret(metin, ses_dosya, ses, hiz))
            log.info("Ses çalınıyor (Baofeng VOX ile yayın)...")
            ses_cal(ses_dosya)
            log.info("Anons tamamlandı.")
        except Exception as e:
            log.error("TTS hatası: %s", e)
        finally:
            try:
                if os.path.exists(ses_dosya):
                    os.remove(ses_dosya)
            except OSError:
                pass
    else:
        log.warning("edge-tts yüklü değil veya --sessiz modu aktif.")


# ── Zamanlayıcı ──────────────────────────────────────────────────────────────


def zamanlayici(ses, hiz, sadece_sari=False):
    """Belirtilen saatlerde anons yapar."""
    log.info("=" * 60)
    log.info("MGM Meteorolojik Uyarı Telsiz Sistemi")
    log.info("Anons saatleri: %s", ", ".join(f"{s:02d}:00" for s in ANONS_SAATLERI))
    log.info("Ses: %s | Hız: %s", ses, hiz)
    log.info("Sadece sarı: %s", "Evet" if sadece_sari else "Hayır (tümü)")
    log.info("Baofeng'de VOX'un açık olduğundan emin olun!")
    log.info("Çıkmak için Ctrl+C")
    log.info("=" * 60)

    yapilan = set()

    try:
        while True:
            simdi = datetime.now(tz=TR_SAAT)
            bugun = simdi.strftime("%Y-%m-%d")
            saat = simdi.hour
            dakika = simdi.minute

            if saat in ANONS_SAATLERI and dakika < 5:
                anahtar = f"{bugun}-{saat}"
                if anahtar not in yapilan:
                    yapilan.add(anahtar)
                    log.info("Anons zamanı: %02d:00", saat)
                    anons_yap(ses=ses, hiz=hiz, sadece_sari=sadece_sari)

            # Gece yarısı temizlik
            if saat == 0 and dakika == 0:
                yapilan.clear()

            time.sleep(30)

    except KeyboardInterrupt:
        log.info("\nKullanıcı tarafından durduruldu.")


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="MGM Meteorolojik Uyarı → Telsiz Seslendirici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python sari_uyari.py                          # Zamanlayıcı (10, 12, 14, 16)
  python sari_uyari.py --tek-sefer              # Bir kez seslendir
  python sari_uyari.py --tek-sefer --sessiz     # Sadece ekrana yaz
  python sari_uyari.py --ses-tipi kadin         # Kadın sesi ile
  python sari_uyari.py --sadece-sari            # Sadece sarı uyarılar
        """,
    )
    parser.add_argument(
        "--tek-sefer", "-t",
        action="store_true",
        help="Uyarıları bir kez çek, seslendir ve çık.",
    )
    parser.add_argument(
        "--sessiz", "-s",
        action="store_true",
        help="Ses çalmadan sadece ekrana yaz.",
    )
    parser.add_argument(
        "--sadece-sari",
        action="store_true",
        help="Sadece sarı uyarıları seslendir (turuncu/kırmızı dahil etme).",
    )
    parser.add_argument(
        "--ses-tipi",
        default="erkek",
        choices=["erkek", "kadin"],
        help="Ses tipi (varsayılan: erkek)",
    )
    parser.add_argument(
        "--ses-hizi",
        default="-10%",
        help="Konuşma hızı (varsayılan: -10%%, yavaş: -20%%, hızlı: +10%%)",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Debug logları aç",
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
