# 🚀 Render.com'a Deploy

PWA'yı internete koyup Win7 dahil her cihazdan tarayıcıdan erişmek için.

## ⚡ Hızlı Adımlar (10 dk)

### 1) GitHub hesabı + repo oluştur

1. https://github.com/signup (ücretsiz)
2. Yeni repo: https://github.com/new → ad: `deprem-pwa` → **Private** seç → Create

### 2) Bu klasörü GitHub'a yükle

PowerShell'de bu klasörde:

```powershell
git init
git add .
git commit -m "ilk surum"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADIN/deprem-pwa.git
git push -u origin main
```

> Eğer git kurulu değilse: https://git-scm.com/download/win

### 3) Render.com hesabı

1. https://render.com → "Get Started" → GitHub ile giriş yap
2. Dashboard → **New +** → **Web Service**
3. GitHub repo'nu bağla → `deprem-pwa` seç
4. Render `render.yaml` dosyasını otomatik tanır
5. **Create Web Service** → 2-4 dk bekle

### 4) Hazır! 🎉

URL şuna benzer olur:
```
https://deprem-pwa.onrender.com
```

Bu adresi:
- 📱 Telefonda aç → "Ana ekrana ekle" → PWA olarak kurulur
- 💻 Win7'de Chrome'da aç → kısayol oluştur
- 🔗 Başkalarıyla paylaş

## 📝 Notlar

### Ücretsiz tier sınırları
- **750 saat/ay** (1 servis 24/7 yeterli)
- **15 dk hareketsizlik = uyku** (ilk istek 30 sn alır, sonra hızlı)
- Uyumayı önlemek için: https://uptimerobot.com (5 dk'da bir ping)

### Ses neden daha iyi olacak?
- **Yerel Win7 program**: pyttsx3 (robotik Microsoft sesi)
- **PWA tarayıcıda**: Chrome'un Google Türkçe sesi (çok daha doğal)
- **Telefonda**: Android/iOS native Türkçe sesi (en iyi)

### Güncelleme yapma
Kodda değişiklik yaptıktan sonra:
```powershell
git add .
git commit -m "guncelleme"
git push
```
Render otomatik yeni versiyonu deploy eder (2-3 dk).

### Sorun çözme
Render dashboard → servis adı → **Logs** sekmesi: hata mesajları orada.

## 🔒 Güvenlik
- AFAD/Kandilli zaten **kamuya açık** veri, gizlilik sorunu yok.
- Sunucuda kişisel veri SAKLANMIYOR.
- Tüm ayarlar tarayıcıda (localStorage) tutulur.

## Alternatif: Railway.app

Aynı prensiple çalışır, $5 ücretsiz kredi/ay verir, uyumaz:
1. https://railway.app → GitHub login
2. New Project → Deploy from GitHub
3. Repo seç → otomatik deploy
