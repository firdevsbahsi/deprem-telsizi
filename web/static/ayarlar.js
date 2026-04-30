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
  const sifirla = $("sifirla");
  // Test paneli
  const testSes = $("test-ses");
  const testBip = $("test-bip");
  const testTitres = $("test-titres");
  const testTam = $("test-tam");
  const testMesaj = $("test-mesaj");
  const testOzel = $("test-ozel");
  const testGercek = $("test-gercek");
  const testDurum = $("test-durum");

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

  // ── Test paneli yardımcıları ──────────────────────────
  let audioCtx = null;
  function bipCal() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const simdi = audioCtx.currentTime;
      [0, 0.22].forEach((gec, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sine";
        osc.frequency.value = 880 + i * 220;
        gain.gain.setValueAtTime(0.0001, simdi + gec);
        gain.gain.exponentialRampToValueAtTime(0.35, simdi + gec + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, simdi + gec + 0.18);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(simdi + gec);
        osc.stop(simdi + gec + 0.2);
      });
    } catch (e) {}
  }

  function konus(metin) {
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(metin);
      u.lang = "tr-TR";
      u.rate = parseFloat(sesHiz.value) || 1.0;
      const ad = sesSecim.value;
      if (ad) {
        const v = speechSynthesis.getVoices().find(x => x.name === ad);
        if (v) u.voice = v;
      }
      u.onend = () => resolve();
      u.onerror = () => resolve();
      speechSynthesis.cancel();
      speechSynthesis.speak(u);
    });
  }

  function durum(s, renk) {
    testDurum.textContent = s;
    testDurum.style.color = renk || "";
  }

  // Buton 1: Örnek anons
  testSes.addEventListener("click", async () => {
    durum("Konuşuyor…", "#fbbf24");
    await konus("Bu bir test. Afet ve Acil Durum Başkanlığı verilerine göre saat 12:00 sularında İstanbul ve çevresinde 3.5 büyüklüğünde yer sarsıntısı meydana gelmiştir.");
    durum("✓ Tamamlandı", "#22c55e");
  });

  // Buton 2: Sadece bip
  testBip.addEventListener("click", () => {
    bipCal();
    durum("✓ Bip çalındı", "#22c55e");
  });

  // Buton 3: Titreşim
  testTitres.addEventListener("click", () => {
    if ("vibrate" in navigator) {
      navigator.vibrate([200, 100, 200, 100, 400]);
      durum("✓ Titreşim gönderildi (telefonda hissedilir)", "#22c55e");
    } else {
      durum("⚠ Bu cihaz titreşim desteklemiyor", "#ef4444");
    }
  });

  // Buton 4: Tam simülasyon (gerçek deprem alarmı gibi)
  testTam.addEventListener("click", async () => {
    durum("🚨 SİMÜLASYON BAŞLADI", "#ef4444");
    bipCal();
    if ("vibrate" in navigator) navigator.vibrate([200, 100, 200, 100, 400]);
    await new Promise(r => setTimeout(r, 700));
    await konus("Dikkat. Bu bir test simülasyonudur. Afet ve Acil Durum Başkanlığı verilerine göre saat " +
      new Date().toLocaleTimeString("tr-TR", {hour:"2-digit", minute:"2-digit"}) +
      " sularında Marmara Denizi ve çevresinde 5.2 büyüklüğünde yer sarsıntısı meydana gelmiştir.");
    durum("✓ Simülasyon tamamlandı", "#22c55e");
  });

  // Özel mesaj
  testOzel.addEventListener("click", async () => {
    const m = (testMesaj.value || "").trim();
    if (!m) { durum("⚠ Önce bir metin yaz", "#ef4444"); return; }
    durum("Konuşuyor…", "#fbbf24");
    await konus(m);
    durum("✓ Tamamlandı", "#22c55e");
  });

  // Gerçek deprem
  testGercek.addEventListener("click", async () => {
    durum("📡 Deprem verisi çekiliyor…", "#fbbf24");
    testGercek.disabled = true;
    try {
      const min = oku("ayar_min", 2.0);
      const r = await fetch("/api/depremler?min=" + min, { cache: "no-store" });
      const v = await r.json();
      if (!v.ok || !v.depremler || v.depremler.length === 0) {
        durum("⚠ Bu eşikte deprem yok (min " + min + ")", "#ef4444");
      } else {
        const d = v.depremler[0];
        bipCal();
        if ("vibrate" in navigator) navigator.vibrate([200, 100, 200]);
        await new Promise(rr => setTimeout(rr, 600));
        const saat = (d.tarih || "").split(" ")[1]?.substring(0,5) || "";
        const kurum = d.kaynak === "Kandilli"
          ? "Kandilli Rasathanesi verilerine göre"
          : "Afet ve Acil Durum Başkanlığı verilerine göre";
        durum(`🔊 ${d.buyukluk.toFixed(1)} ${d.yer.substring(0,40)}…`, "#22c55e");
        await konus(`${kurum} saat ${saat} sularında ${d.yer} ve çevresinde ${d.buyukluk.toFixed(1)} büyüklüğünde yer sarsıntısı meydana gelmiştir.`);
        durum("✓ Tamamlandı", "#22c55e");
      }
    } catch (e) {
      durum("⚠ Bağlantı hatası: " + e.message, "#ef4444");
    }
    testGercek.disabled = false;
  });
  sifirla.addEventListener("click", () => {
    if (!confirm("Tüm ayarlar sıfırlansın mı?")) return;
    ["ayar_min","ayar_konum_aktif","ayar_lat","ayar_lon","ayar_yaricap","ayar_ses_hiz","ayar_ses_adi"]
      .forEach(k => localStorage.removeItem(k));
    location.reload();
  });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
})();
