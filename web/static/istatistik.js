// İstatistik sayfası
(function () {
  "use strict";

  let chart = null;
  let aktifMin = 0;

  async function yukle() {
    try {
      const r = await fetch(`/api/istatistik?min=${aktifMin}`, { cache: "no-store" });
      const v = await r.json();
      if (!v.ok) return;

      document.getElementById("ozet-toplam").textContent = v.toplam;
      document.getElementById("ozet-ortalama").textContent = v.ortalama.toFixed(2);

      if (v.en_buyuk) {
        document.getElementById("ozet-enbuyuk").textContent = `M${v.en_buyuk.buyukluk.toFixed(1)}`;
        document.getElementById("ozet-enbuyuk-yer").textContent = v.en_buyuk.yer;
      } else {
        document.getElementById("ozet-enbuyuk").textContent = "—";
        document.getElementById("ozet-enbuyuk-yer").textContent = "Veri yok";
      }

      // Bölgeler
      const liste = document.getElementById("aktif-bolgeler");
      if (v.en_aktif_bolgeler.length === 0) {
        liste.innerHTML = "<li>Veri yok</li>";
      } else {
        liste.innerHTML = v.en_aktif_bolgeler
          .map(b => `<li><span class="b-ad">${b.bolge}</span><span class="b-sayi">${b.sayi}</span></li>`)
          .join("");
      }

      // Grafik
      const etiketler = [];
      const simdi = new Date();
      for (let i = 23; i >= 0; i--) {
        const d = new Date(simdi.getTime() - i * 3600000);
        etiketler.push(d.getHours().toString().padStart(2, "0") + ":00");
      }

      const ctx = document.getElementById("chart-saatlik");
      if (chart) chart.destroy();
      chart = new Chart(ctx, {
        type: "bar",
        data: {
          labels: etiketler,
          datasets: [{
            label: "Deprem sayısı",
            data: v.saatlik,
            backgroundColor: "#0ea5e9",
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#94a3b8", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
            y: { ticks: { color: "#94a3b8", precision: 0 }, grid: { color: "#334155" } },
          },
        },
      });
    } catch (e) {
      console.error(e);
    }
  }

  document.querySelectorAll(".ist-sec").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ist-sec").forEach(b => b.classList.remove("aktif"));
      btn.classList.add("aktif");
      aktifMin = parseFloat(btn.dataset.min);
      yukle();
    });
  });

  yukle();
  setInterval(yukle, 60000);

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
})();
