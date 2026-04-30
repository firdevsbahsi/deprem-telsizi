// Tema yöneticisi — açık/koyu/otomatik
// Tüm sayfalarda <head> içinde inline çalıştırılır (FOUC önler)
(function () {
  "use strict";
  const KEY = "ayar_tema"; // "acik" | "koyu" | "oto"
  function uygula(tema) {
    const sistem = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
    const acik = (tema === "acik") || (tema === "oto" && sistem);
    document.body.classList.toggle("tema-acik", acik);
    // Theme-color meta (tarayıcı çubuk rengi)
    let meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", acik ? "#ffffff" : "#0f172a");
  }
  function oku() {
    try { return JSON.parse(localStorage.getItem(KEY)) || "oto"; } catch (e) { return "oto"; }
  }
  function yaz(v) { localStorage.setItem(KEY, JSON.stringify(v)); }

  function init() { uygula(oku()); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Sistem teması değişirse oto modda yeniden uygula
  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    mq.addEventListener && mq.addEventListener("change", () => {
      if (oku() === "oto") uygula("oto");
    });
  }

  // Global API
  window.TemaYonetici = {
    al: oku,
    ayarla: (v) => { yaz(v); uygula(v); },
    dongu: () => {
      // koyu → acik → oto → koyu
      const sira = ["koyu", "acik", "oto"];
      const su = oku();
      const yeni = sira[(sira.indexOf(su) + 1) % sira.length];
      yaz(yeni); uygula(yeni);
      return yeni;
    },
    simge: () => ({ koyu: "🌙", acik: "☀️", oto: "🔄" })[oku()] || "🌙",
  };
})();
