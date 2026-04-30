#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test modu — tüm büyüklükleri sürekli izler, yeni deprem gelince sesli okur.
Büyüklük filtresi YOK (M0.0+). Ctrl+C ile durdurulur.
"""

import time
import logging

from deprem_telsiz import (
    html_den_cek,
    kandilli_den_cek,
    _tarih_parse,
    _tarihe_gore_sirala,
    _tekrarlari_kaldir,
    _tarih_saat_al,
    _tarih_gun_al,
    _tarih_filtrele,
    sesli_mesaj_olustur,
    BaofengGonderici,
)

log = logging.getLogger("test_veri")

KONTROL_ARASI = 60  # saniye


def veri_cek():
    """AFAD + Kandilli'den tüm depremleri çeker, birleştirir, sıralar."""
    tum = []
    afad = html_den_cek(min_buyukluk=0.0)
    if afad:
        tum.extend(afad)
    kandilli = kandilli_den_cek(min_buyukluk=0.0)
    if kandilli:
        tum.extend(kandilli)
    if not tum:
        return []
    tum = _tekrarlari_kaldir(tum)
    tum = _tarihe_gore_sirala(tum)
    tum = _tarih_filtrele(tum, son_saat=24)
    return tum


def main():
    print("\n" + "=" * 70)
    print(" TEST SÜREKLİ İZLEME — Tüm büyüklükler (filtre yok)")
    print(" Yeni deprem geldiğinde sesli okur. Ctrl+C ile durdur.")
    print("=" * 70)

    gonderici = BaofengGonderici(ses_hizi="+0%", ses_tipi="erkek", test_modu=False)
    son_tarih = None  # Başlangıçtaki en son depremin tarihi
    ilk = True

    try:
        while True:
            depremler = veri_cek()

            if not depremler:
                log.warning("Veri alınamadı, %d sn sonra tekrar...", KONTROL_ARASI)
                time.sleep(KONTROL_ARASI)
                continue

            if ilk:
                # İlk çalışmada en son depremin tarihini kaydet ve oku
                son = depremler[0]
                son_tarih = _tarih_parse(son["tarih"])
                gun = _tarih_gun_al(son["tarih"])
                saat = _tarih_saat_al(son["tarih"])
                print(f"\n  Son deprem: M{son['buyukluk']:.1f} | {gun} {saat} | {son['yer']}")
                mesaj = sesli_mesaj_olustur(son)
                gonderici.gonder(mesaj)

                print(f"\n  Başlangıç tarihi kaydedildi: {gun} {saat}")
                print(f"  Bundan sonra sadece bu tarihten YENİ depremler okunacak...")
                ilk = False
            else:
                # Sadece son_tarih'ten sonraki depremleri oku
                yeniler = []
                for d in depremler:
                    d_tarih = _tarih_parse(d["tarih"])
                    if d_tarih and son_tarih and d_tarih > son_tarih:
                        yeniler.append(d)

                if yeniler:
                    # En eskiden en yeniye oku
                    yeniler.reverse()
                    for d in yeniler:
                        gun = _tarih_gun_al(d["tarih"])
                        saat = _tarih_saat_al(d["tarih"])
                        print(f"\n  *** YENİ DEPREM: M{d['buyukluk']:.1f} | {gun} {saat} | {d['yer']}")
                        mesaj = sesli_mesaj_olustur(d)
                        gonderici.gonder(mesaj)
                    # En son depremin tarihini güncelle
                    son_tarih = _tarih_parse(yeniler[-1]["tarih"])

            time.sleep(KONTROL_ARASI)

    except KeyboardInterrupt:
        print("\n\n  Durduruldu.")
    finally:
        gonderici.kapat()


if __name__ == "__main__":
    main()
