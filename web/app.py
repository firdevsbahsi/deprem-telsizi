#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AFAD Deprem PWA — Flask Sunucusu
=================================
Üç ayrı eşik (M1+, M2+, M3+) için ayrı arayüzler sunar.
deprem_telsiz.py'nin veri çekme fonksiyonlarını kullanır.

Çalıştır:
    python web/app.py
Sonra tarayıcıda aç:
    http://localhost:5000           (ana seçim ekranı)
    http://localhost:5000/m1        (M1.0+ izleme)
    http://localhost:5000/m2        (M2.0+ izleme)
    http://localhost:5000/m3        (M3.0+ izleme)

PWA: tarayıcıdan "Ana ekrana ekle" ile telefona kurulabilir.
"""

import os
import sys
import time
import math
import threading
from datetime import datetime, timezone, timedelta


def _haversine_km(lat1, lon1, lat2, lon2):
    """İki nokta arası mesafe (km)."""
    R = 6371.0
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

# Üst klasördeki deprem_telsiz.py'yi import edebilmek için
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from flask import Flask, render_template, jsonify, request, send_from_directory, abort

from deprem_telsiz import (
    html_den_cek,
    kandilli_den_cek,
    _tarihe_gore_sirala,
    _tekrarlari_kaldir,
    _tarih_filtrele,
    _tarih_parse,
)

app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Veri Önbelleği + Arka Plan Thread ────────────────────────────────────────
# API çağrılarını anında yanıtlamak için arka planda her 20 sn'de bir veri
# çekilir; kullanıcı bekletilmez.
_CACHE = {"zaman": 0, "veri": [], "guncelleme": ""}
_CACHE_LOCK = threading.Lock()
_ARKA_PLAN_ARALIK = 20  # saniye

GECERLI_ESIKLER = {1.0, 2.0, 3.0}


def _veri_cek_simdi():
    """AFAD + Kandilli'yi çek, birleştir, sırala. Senkron."""
    tum = []
    afad = html_den_cek(min_buyukluk=0.0)
    if afad:
        tum.extend(afad)
    kandilli = kandilli_den_cek(min_buyukluk=0.0)
    if kandilli:
        tum.extend(kandilli)
    if tum:
        tum = _tekrarlari_kaldir(tum)
        tum = _tarihe_gore_sirala(tum)
        tum = _tarih_filtrele(tum, son_saat=24)
    return tum


def _arka_plan_dongu():
    """Sürekli çalışır, _CACHE'i günceller."""
    while True:
        try:
            yeni = _veri_cek_simdi()
            tr_saat = timezone(timedelta(hours=3))
            with _CACHE_LOCK:
                _CACHE["veri"] = yeni
                _CACHE["zaman"] = time.time()
                _CACHE["guncelleme"] = datetime.now(tz=tr_saat).strftime("%H:%M:%S")
        except Exception as e:
            print(f"[arka-plan] hata: {e}")
        time.sleep(_ARKA_PLAN_ARALIK)


def _veri_cek_onbellekli():
    """Cache'den hızlıca veriyi döner. İlk istekte boşsa senkron çeker."""
    with _CACHE_LOCK:
        if _CACHE["veri"]:
            return _CACHE["veri"]
    # İlk seferde cache boş — senkron çek
    veri = _veri_cek_simdi()
    tr_saat = timezone(timedelta(hours=3))
    with _CACHE_LOCK:
        _CACHE["veri"] = veri
        _CACHE["zaman"] = time.time()
        _CACHE["guncelleme"] = datetime.now(tz=tr_saat).strftime("%H:%M:%S")
    return veri


# Arka plan thread'i sunucu açılır açılmaz başlat
_arka_plan_thread = threading.Thread(target=_arka_plan_dongu, daemon=True)
_arka_plan_thread.start()


def _deprem_id(d):
    """Bir depreme tekrarsız kimlik üretir (frontend'de yeni deprem tespiti için)."""
    return f"{d.get('tarih','')}|{d.get('enlem','')}|{d.get('boylam','')}|{d.get('buyukluk','')}"


def _serialize(d):
    """JSON için temizlenmiş deprem objesi."""
    return {
        "id": _deprem_id(d),
        "tarih": str(d.get("tarih", "")),
        "buyukluk": float(d.get("buyukluk", 0)),
        "yer": str(d.get("yer", "")),
        "enlem": str(d.get("enlem", "")),
        "boylam": str(d.get("boylam", "")),
        "derinlik": str(d.get("derinlik", "")),
        "tip": str(d.get("tip", "")),
        "kaynak": str(d.get("kaynak", "")),
    }


# ── Sayfalar ─────────────────────────────────────────────────────────────────


@app.route("/")
def ana_sayfa():
    return render_template("index.html")


@app.route("/m<int:esik>")
def izleme(esik):
    if float(esik) not in GECERLI_ESIKLER:
        abort(404)
    baslik_renk = {1: "#22c55e", 2: "#f59e0b", 3: "#ef4444"}[esik]
    return render_template("izleme.html", esik=esik, baslik_renk=baslik_renk,
                           baslik=f"M{esik}.0+", ozel=False)


@app.route("/ozel")
def ozel_izleme():
    """Ayarlardan gelen serbest eşikle izleme."""
    return render_template("izleme.html", esik=0, baslik_renk="#0ea5e9",
                           baslik="Özel İzleme", ozel=True)


@app.route("/ayarlar")
def ayarlar():
    return render_template("ayarlar.html")


@app.route("/istatistik")
def istatistik():
    return render_template("istatistik.html")


@app.route("/harita")
def harita():
    return render_template("harita.html")


# ── API ──────────────────────────────────────────────────────────────────────


@app.route("/api/depremler")
def api_depremler():
    try:
        min_b = float(request.args.get("min", "0"))
    except ValueError:
        min_b = 0.0

    # Bölge filtreleri (opsiyonel): merkez ± yarıçap (km)
    try:
        merkez_lat = float(request.args.get("lat", ""))
        merkez_lon = float(request.args.get("lon", ""))
        yaricap = float(request.args.get("r", ""))
    except ValueError:
        merkez_lat = merkez_lon = yaricap = None

    veri = _veri_cek_onbellekli()
    filtreli = []
    for d in veri:
        if float(d.get("buyukluk", 0)) < min_b:
            continue
        if merkez_lat is not None and yaricap is not None:
            try:
                dlat = float(d.get("enlem", 0))
                dlon = float(d.get("boylam", 0))
                if _haversine_km(merkez_lat, merkez_lon, dlat, dlon) > yaricap:
                    continue
            except (ValueError, TypeError):
                continue
        filtreli.append(_serialize(d))

    tr_saat = timezone(timedelta(hours=3))
    return jsonify({
        "ok": True,
        "guncelleme": datetime.now(tz=tr_saat).strftime("%H:%M:%S"),
        "min": min_b,
        "toplam": len(filtreli),
        "depremler": filtreli,
    })


@app.route("/api/istatistik")
def api_istatistik():
    """Son 24 saatlik özet: saatlik dağılım, en aktif bölgeler, en büyük."""
    try:
        min_b = float(request.args.get("min", "0"))
    except ValueError:
        min_b = 0.0

    veri = [d for d in _veri_cek_onbellekli()
            if float(d.get("buyukluk", 0)) >= min_b]

    tr_saat = timezone(timedelta(hours=3))
    simdi = datetime.now(tz=tr_saat)

    # Saatlik kova (son 24 saat, en yeni saat sonda)
    saatlik = [0] * 24
    bolge_sayac = {}
    en_buyuk = None
    toplam_mag = 0.0
    sayi = 0

    for d in veri:
        dt = _tarih_parse(d.get("tarih", ""))
        if dt is None:
            continue
        fark_saat = (simdi - dt).total_seconds() / 3600.0
        if 0 <= fark_saat < 24:
            idx = 23 - int(fark_saat)
            if 0 <= idx < 24:
                saatlik[idx] += 1
        # Bölge: yer stringinin parantez içi (il) ya da ilk kelime
        yer = str(d.get("yer", ""))
        bolge = yer
        if "(" in yer and ")" in yer:
            try:
                bolge = yer[yer.rindex("(") + 1:yer.rindex(")")]
            except ValueError:
                pass
        bolge_sayac[bolge] = bolge_sayac.get(bolge, 0) + 1

        b = float(d.get("buyukluk", 0))
        toplam_mag += b
        sayi += 1
        if en_buyuk is None or b > float(en_buyuk.get("buyukluk", 0)):
            en_buyuk = d

    en_aktif = sorted(bolge_sayac.items(), key=lambda x: x[1], reverse=True)[:5]

    return jsonify({
        "ok": True,
        "toplam": sayi,
        "ortalama": round(toplam_mag / sayi, 2) if sayi else 0,
        "en_buyuk": _serialize(en_buyuk) if en_buyuk else None,
        "saatlik": saatlik,
        "en_aktif_bolgeler": [{"bolge": b, "sayi": s} for b, s in en_aktif],
    })


# ── PWA Dosyaları ────────────────────────────────────────────────────────────


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest",
                               mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    # SW'nin tüm scope'u kontrol etmesi için kökten servis edilmeli
    return send_from_directory(app.static_folder, "sw.js",
                               mimetype="application/javascript")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "icon-192.png",
                               mimetype="image/png")


# ── Ana ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print("=" * 60)
    print(" AFAD Deprem PWA")
    print(f" http://localhost:{port}")
    print(" Telefondan: http://<bilgisayar-ip>:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
