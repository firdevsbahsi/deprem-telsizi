# AFAD Deprem → Baofeng Telsiz Gönderici

AFAD'ın son deprem verilerini otomatik çeker, yeni depremleri tespit eder ve **Baofeng telsiz** üzerinden sesli anons olarak yayınlar.

## Kurulum

```bash
cd afad_telsiz
pip install -r requirements.txt
```

**Türkçe TTS sesi için (önerilir):**
Windows Ayarlar → Zaman ve dil → Konuşma → Ses ekle → **Türkçe** seçin.

## Kullanım

### Test Modu (donanım gerekmez)
```bash
# Son depremleri ekrana bas (sessiz)
python deprem_telsiz.py --tek-sefer

# Sesli test — bilgisayar hoparlöründen okur (Baofeng bağlı değilken test)
python deprem_telsiz.py --baofeng --tek-sefer --adet 3
```

### Baofeng ile Gerçek Kullanım
```bash
# Sürekli izle, yeni depremleri sesli olarak Baofeng'den yayınla
python deprem_telsiz.py --baofeng

# Sadece 3.0+ büyüklüğündekileri, 2 dakikada bir kontrol et
python deprem_telsiz.py --baofeng --min 3.0 --aralik 120

# Konuşma hızını ayarla (yavaş=100, normal=130, hızlı=170)
python deprem_telsiz.py --baofeng --ses-hizi 100
```

## Baofeng Bağlantısı (UV-5R / UV-82 / BF-888S)

### Nasıl Çalışır?
1. Script AFAD'dan yeni deprem tespit eder
2. Deprem bilgisi Türkçe olarak seslendirilir (TTS)
3. Ses, bilgisayarın **kulaklık çıkışından** kablo ile Baofeng'in **mikrofon girişine** gider
4. Baofeng'de **VOX** (ses ile otomatik yayın) açık olmalı → ses algılayınca otomatik yayın yapar

### Kablo Bağlantısı

Baofeng UV-5R / UV-82 **Kenwood K-type 2-pin** konnektör kullanır:

```
Bilgisayar                          Baofeng UV-5R
┌──────────┐                        ┌──────────┐
│ Kulaklık │──── ses kablosu ──────→│ MIC      │ (2.5mm jack)
│ çıkışı   │     (3.5mm→2.5mm)     │ girişi   │
│ (3.5mm)  │                        │          │
└──────────┘                        │ VOX: ON  │
                                    │ Seviye:3 │
                                    └──────────┘
```

### Kablo Yapımı (Kenwood K-plug)

```
3.5mm stereo → 2.5mm mono kablo:

Bilgisayar tarafı (3.5mm)     Baofeng tarafı (2.5mm K-plug)
  Uç (Tip)  ──┐               ┌── Uç (Tip) = MIC
               ├── 10kΩ ──────┤
  Halka (Ring)─┘               └── Gövde (Sleeve) = GND
  Gövde (Sleeve) ─── GND ─────── GND
```

**Önemli:** 10kΩ direnç (veya potansiyometre) ses seviyesini düşürür, Baofeng'in mikrofon girişini korur.

### Baofeng Ayarları

| Ayar | Değer | Açıklama |
|------|-------|----------|
| VOX  | ON    | Ses ile otomatik yayın |
| VOX Level | 3-5 | Hassasiyet (düşük=hassas) |
| Kanal | İstediğiniz frekans | Yayın yapılacak kanal |

**VOX Ayarı:** Menü → 4 (VOX) → 3 veya 4 → Onayla

### Alternatif: Hazır Kablo
- "Baofeng APRS kablosu" veya "Baofeng ses arabirimi kablosu" aratarak hazır kablo bulabilirsiniz
- BTECH APRS-K1, APRS-K2 gibi kablolar doğrudan çalışır

## Mesaj Formatları

**Sesli anons (Baofeng):**
```
Dikkat deprem! Büyüklük 3 nokta 2. Saat 11:58.
Yer: Onikişubat, Kahramanmaraş. Derinlik 7 kilometre.
```

**Metin (seri port / test):**
```
DEPREM! M3.2 | 11:58 | Onikisubat (Kahramanmaras) | Derin:6.99km | 37.86/36.47
```

## Parametreler

| Parametre       | Kısa | Varsayılan | Açıklama                          |
|-----------------|-------|-----------|-----------------------------------|
| `--baofeng`     |       | -         | Baofeng sesli anons modu          |
| `--port`        | `-p`  | (yok)     | Seri port (dijital telsiz)        |
| `--baud`        | `-b`  | 9600      | Baud rate                         |
| `--ses-hizi`    |       | 130       | TTS konuşma hızı (kelime/dk)     |
| `--ses-seviyesi`|       | 1.0       | TTS ses seviyesi (0.0-1.0)       |
| `--min`         | `-m`  | 0.0       | Minimum deprem büyüklüğü         |
| `--aralik`      | `-a`  | 60        | Kontrol aralığı (saniye)          |
| `--tek-sefer`   | `-t`  | -         | Bir kez çek ve çık                |
| `--adet`        | `-n`  | 20        | Tek seferlik modda gösterilecek   |
| `--debug`       | `-d`  | -         | Detaylı log                       |
