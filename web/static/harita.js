// Harita sayfası — Leaflet + Heatmap + Fay Hatları
(function () {
  "use strict";

  const harita = L.map("harita", { zoomControl: true }).setView([39.0, 35.5], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap",
  }).addTo(harita);

  let katman = L.layerGroup().addTo(harita);
  let heatLayer = null;
  let fayLayer = null;
  let sonVeri = [];

  const btnHeat = document.getElementById("btn-heatmap");
  const btnFay = document.getElementById("btn-fay");

  // Türkiye ana fay hatları (basitleştirilmiş) — KAF, DAF, EAF kolları
  // Kaynak: MTA topluluk verilerinden türetilmiş, yaklaşık gösterim
  const FAY_HATLARI = [
    { ad: "Kuzey Anadolu Fayı (KAF)", koor: [
      [40.62, 27.30], [40.74, 28.10], [40.78, 28.85], [40.82, 29.40],
      [40.78, 30.30], [40.74, 31.10], [40.80, 31.90], [40.85, 32.80],
      [40.92, 33.85], [40.98, 35.05], [40.85, 36.10], [40.50, 37.50],
      [40.20, 38.80], [40.05, 39.80], [39.95, 40.80], [39.95, 41.80]
    ]},
    { ad: "Doğu Anadolu Fayı (DAF)", koor: [
      [37.05, 36.20], [37.55, 36.85], [38.05, 37.40], [38.30, 37.80],
      [38.55, 38.40], [38.75, 38.95], [38.95, 39.65], [39.20, 40.30]
    ]},
    { ad: "Batı Anadolu Graben Sistemi", koor: [
      [38.40, 26.85], [38.45, 27.50], [38.50, 28.20], [38.55, 28.95]
    ]},
    { ad: "Ölü Deniz Fayı (güney kol)", koor: [
      [36.20, 36.10], [36.55, 36.20], [36.95, 36.30], [37.05, 36.20]
    ]},
    { ad: "KAF Güney Kolu (Marmara)", koor: [
      [40.62, 27.30], [40.55, 27.85], [40.45, 28.50], [40.38, 29.10],
      [40.42, 29.65], [40.50, 30.20]
    ]},
    { ad: "Eskişehir Fayı", koor: [
      [39.78, 30.50], [39.65, 31.20], [39.50, 31.90], [39.40, 32.60]
    ]},
    { ad: "Tuz Gölü Fayı", koor: [
      [38.55, 33.40], [38.20, 33.55], [37.85, 33.65], [37.50, 33.70]
    ]},
    { ad: "Burdur-Fethiye", koor: [
      [37.70, 30.20], [37.30, 29.85], [36.90, 29.40], [36.65, 29.10]
    ]},
  ];

  function fayKatmanOlustur() {
    const grup = L.layerGroup();
    FAY_HATLARI.forEach(f => {
      const cizgi = L.polyline(f.koor, {
        color: "#fbbf24", weight: 3, opacity: 0.85, dashArray: "6,4"
      });
      cizgi.bindTooltip(f.ad, { sticky: true });
      cizgi.addTo(grup);
    });
    return grup;
  }

  function renkSec(b) {
    if (b >= 5) return "#7f1d1d";
    if (b >= 4) return "#dc2626";
    if (b >= 3) return "#f97316";
    if (b >= 2) return "#f59e0b";
    return "#22c55e";
  }
  function yariCap(b) {
    return Math.max(6, Math.min(40, 4 + b * 4));
  }

  function dairesiCiz() {
    katman.clearLayers();
    sonVeri.forEach(d => {
      const lat = parseFloat(d.enlem);
      const lon = parseFloat(d.boylam);
      if (isNaN(lat) || isNaN(lon)) return;
      const c = L.circleMarker([lat, lon], {
        radius: yariCap(d.buyukluk),
        color: renkSec(d.buyukluk),
        fillColor: renkSec(d.buyukluk),
        fillOpacity: 0.55,
        weight: 2,
      });
      c.bindPopup(`
        <b>M${d.buyukluk.toFixed(1)}</b> — ${d.yer}<br>
        🕒 ${d.tarih}<br>
        📐 Derinlik: ${d.derinlik} km<br>
        📍 ${parseFloat(d.enlem).toFixed(3)}, ${parseFloat(d.boylam).toFixed(3)}<br>
        <small>Kaynak: ${d.kaynak}</small>
      `);
      c.addTo(katman);
    });
  }

  function heatmapCiz() {
    if (heatLayer) { harita.removeLayer(heatLayer); heatLayer = null; }
    const noktalar = sonVeri.map(d => {
      const lat = parseFloat(d.enlem), lon = parseFloat(d.boylam);
      if (isNaN(lat) || isNaN(lon)) return null;
      // Yoğunluk = büyüklük ile orantılı (1.0 → ölçek)
      const yog = Math.max(0.2, Math.min(1.0, d.buyukluk / 5));
      return [lat, lon, yog];
    }).filter(Boolean);
    if (typeof L.heatLayer !== "function") return;
    heatLayer = L.heatLayer(noktalar, {
      radius: 30, blur: 25, maxZoom: 9,
      gradient: { 0.2: "#22c55e", 0.4: "#f59e0b", 0.6: "#f97316", 0.8: "#dc2626", 1.0: "#7f1d1d" }
    }).addTo(harita);
  }

  async function yukle() {
    const min = document.getElementById("harita-min").value;
    document.getElementById("harita-durum").textContent = "Yükleniyor…";
    try {
      const r = await fetch(`/api/depremler?min=${min}`, { cache: "no-store" });
      const v = await r.json();
      sonVeri = v.depremler || [];
      dairesiCiz();
      if (heatLayer) heatmapCiz();
      document.getElementById("harita-durum").textContent =
        `${v.toplam} deprem · ${v.guncelleme}`;
    } catch (e) {
      document.getElementById("harita-durum").textContent = "Hata";
    }
  }

  // Toggle: Heatmap
  btnHeat.addEventListener("click", () => {
    if (heatLayer) {
      harita.removeLayer(heatLayer);
      heatLayer = null;
      btnHeat.classList.remove("aktif");
    } else {
      heatmapCiz();
      btnHeat.classList.add("aktif");
    }
  });

  // Toggle: Fay Hatları
  btnFay.addEventListener("click", () => {
    if (fayLayer) {
      harita.removeLayer(fayLayer);
      fayLayer = null;
      btnFay.classList.remove("aktif");
    } else {
      fayLayer = fayKatmanOlustur();
      fayLayer.addTo(harita);
      btnFay.classList.add("aktif");
    }
  });

  document.getElementById("harita-min").addEventListener("change", yukle);
  yukle();
  setInterval(yukle, 60000);

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
})();
