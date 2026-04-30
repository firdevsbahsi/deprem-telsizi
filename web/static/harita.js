// Harita sayfası — Leaflet
(function () {
  "use strict";

  const harita = L.map("harita", { zoomControl: true }).setView([39.0, 35.5], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap",
  }).addTo(harita);

  let katman = L.layerGroup().addTo(harita);

  function renkSec(b) {
    if (b >= 4) return "#dc2626";
    if (b >= 3) return "#f97316";
    if (b >= 2) return "#f59e0b";
    return "#22c55e";
  }
  function yariCap(b) {
    return Math.max(6, Math.min(40, 4 + b * 4));
  }

  async function yukle() {
    const min = document.getElementById("harita-min").value;
    document.getElementById("harita-durum").textContent = "Yükleniyor…";
    try {
      const r = await fetch(`/api/depremler?min=${min}`, { cache: "no-store" });
      const v = await r.json();
      katman.clearLayers();

      v.depremler.forEach(d => {
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
          ${d.tarih}<br>
          Derinlik: ${d.derinlik} km<br>
          <small>${d.kaynak}</small>
        `);
        c.addTo(katman);
      });

      document.getElementById("harita-durum").textContent =
        `${v.toplam} deprem · ${v.guncelleme}`;
    } catch (e) {
      document.getElementById("harita-durum").textContent = "Hata";
    }
  }

  document.getElementById("harita-min").addEventListener("change", yukle);
  yukle();
  setInterval(yukle, 60000);

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
})();
