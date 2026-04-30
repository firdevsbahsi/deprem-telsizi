// AFAD Deprem PWA — Service Worker
// Stratejisi:
//  - HTML/CSS/JS/manifest: cache-first (offline çalışsın)
//  - /api/* : network-only (her zaman taze veri)

const CACHE = "deprem-pwa-v19";
const ON_BELLEK_DOSYALAR = [
  "/",
  "/m1",
  "/m2",
  "/m3",
  "/ozel",
  "/ayarlar",
  "/istatistik",
  "/harita",
  "/static/style.css",
  "/static/app.js",
  "/static/ayarlar.js",
  "/static/istatistik.js",
  "/static/harita.js",
  "/manifest.webmanifest",
  "/static/icon-192.png",
  "/static/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ON_BELLEK_DOSYALAR).catch(() => null))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((adlar) =>
      Promise.all(adlar.filter((a) => a !== CACHE).map((a) => caches.delete(a)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API → her zaman ağdan
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(event.request).catch(() => new Response(
      JSON.stringify({ ok: false, depremler: [], hata: "offline" }),
      { headers: { "Content-Type": "application/json" } }
    )));
    return;
  }

  // Diğerleri: önce cache, yoksa ağ
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((resp) => {
        if (resp && resp.status === 200 && url.origin === location.origin) {
          const klon = resp.clone();
          caches.open(CACHE).then((c) => c.put(event.request, klon));
        }
        return resp;
      }).catch(() => cached);
    })
  );
});
