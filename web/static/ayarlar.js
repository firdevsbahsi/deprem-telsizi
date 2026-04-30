// Ayarlar sayfası — localStorage'a yazar
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const minSlider = $("min-buyukluk");
  const minDeger = $("min-deger");
  const konumAktif = $("konum-aktif");
  const yaricapRow = $("yaricap-row");
  const yaricap = $("yaricap");
  const yaricapDeger = $("yaricap-deger");
  const konumAl = $("konum-al");
  const konumBilgi = $("konum-bilgi");
  const sesHiz = $("ses-hiz");
  const sesSecim = $("ses-secim");
  const sesTest = $("ses-test");
  const sifirla = $("sifirla");

  function oku(k, v) {
    try {
      const x = localStorage.getItem(k);
      if (x === null) return v;
      return JSON.parse(x);
    } catch (e) { return v; }
  }
  function yaz(k, v) { localStorage.setItem(k, JSON.stringify(v)); }

  // Yükle
  minSlider.value = oku("ayar_min", 2.0);
  minDeger.textContent = parseFloat(minSlider.value).toFixed(1);
  konumAktif.checked = oku("ayar_konum_aktif", false);
  yaricap.value = oku("ayar_yaricap", 500);
  yaricapDeger.textContent = yaricap.value + " km";
  yaricapRow.style.display = konumAktif.checked ? "" : "none";
  sesHiz.value = oku("ayar_ses_hiz", 1.0);

  const lat = oku("ayar_lat", null);
  const lon = oku("ayar_lon", null);
  if (lat != null && lon != null) {
    konumBilgi.textContent = `Konum: ${lat.toFixed(3)}, ${lon.toFixed(3)}`;
  }

  // Ses listesi
  function sesleriYukle() {
    const sesler = speechSynthesis.getVoices().filter(v => /tr/i.test(v.lang));
    sesSecim.innerHTML = '<option value="">(otomatik tr-TR)</option>' +
      sesler.map(v => `<option value="${v.name}">${v.name}</option>`).join("");
    sesSecim.value = oku("ayar_ses_adi", "");
  }
  if ("speechSynthesis" in window) {
    sesleriYukle();
    speechSynthesis.onvoiceschanged = sesleriYukle;
  }

  // Olaylar
  minSlider.addEventListener("input", () => {
    minDeger.textContent = parseFloat(minSlider.value).toFixed(1);
    yaz("ayar_min", parseFloat(minSlider.value));
  });
  konumAktif.addEventListener("change", () => {
    yaz("ayar_konum_aktif", konumAktif.checked);
    yaricapRow.style.display = konumAktif.checked ? "" : "none";
  });
  yaricap.addEventListener("input", () => {
    yaricapDeger.textContent = yaricap.value + " km";
    yaz("ayar_yaricap", parseInt(yaricap.value, 10));
  });
  konumAl.addEventListener("click", () => {
    if (!("geolocation" in navigator)) {
      konumBilgi.textContent = "Bu cihaz konum desteklemiyor.";
      return;
    }
    konumBilgi.textContent = "Konum alınıyor…";
    navigator.geolocation.getCurrentPosition((p) => {
      yaz("ayar_lat", p.coords.latitude);
      yaz("ayar_lon", p.coords.longitude);
      konumBilgi.textContent = `Konum: ${p.coords.latitude.toFixed(3)}, ${p.coords.longitude.toFixed(3)}`;
    }, (e) => {
      konumBilgi.textContent = "Konum alınamadı: " + e.message;
    }, { enableHighAccuracy: false, timeout: 10000 });
  });
  sesHiz.addEventListener("change", () => yaz("ayar_ses_hiz", parseFloat(sesHiz.value)));
  sesSecim.addEventListener("change", () => yaz("ayar_ses_adi", sesSecim.value));
  sesTest.addEventListener("click", () => {
    const u = new SpeechSynthesisUtterance(
      "Bu bir test. Afet ve Acil Durum Başkanlığı verilerine göre saat 12:00 sularında İstanbul ve çevresinde 3.5 büyüklüğünde yer sarsıntısı meydana gelmiştir."
    );
    u.lang = "tr-TR";
    u.rate = parseFloat(sesHiz.value);
    const ad = sesSecim.value;
    if (ad) {
      const v = speechSynthesis.getVoices().find(x => x.name === ad);
      if (v) u.voice = v;
    }
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  });
  sifirla.addEventListener("click", () => {
    if (!confirm("Tüm ayarlar sıfırlansın mı?")) return;
    ["ayar_min","ayar_konum_aktif","ayar_lat","ayar_lon","ayar_yaricap","ayar_ses_hiz","ayar_ses_adi"]
      .forEach(k => localStorage.removeItem(k));
    location.reload();
  });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
})();
