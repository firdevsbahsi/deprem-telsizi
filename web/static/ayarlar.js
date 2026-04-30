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
  const sesSeviyesi = $("ses-seviyesi");
  const sesSecim = $("ses-secim");
  const sesMotor = $("ses-motor");
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
  sesSeviyesi.value = oku("ayar_ses_seviyesi", 1.0);
  // Motor: "tarayici" | "sunucu" + isim "ahmet"|"emel"
  (function () {
    const motor = oku("ayar_ses_motor", "tarayici");
    const isim = oku("ayar_ses_motor_isim", "ahmet");
    if (sesMotor) {
      if (motor === "sunucu") sesMotor.value = (isim === "emel") ? "sunucu-emel" : "sunucu-ahmet";
      else sesMotor.value = "tarayici";
    }
  })();

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
  sesSeviyesi.addEventListener("change", () => {
    yaz("ayar_ses_seviyesi", parseFloat(sesSeviyesi.value));
    if (masterGain) masterGain.gain.value = 0.18 * (parseFloat(sesSeviyesi.value) || 1.0);
  });
  sesSecim.addEventListener("change", () => yaz("ayar_ses_adi", sesSecim.value));
  if (sesMotor) {
    sesMotor.addEventListener("change", () => {
      const v = sesMotor.value;
      if (v === "sunucu-ahmet") { yaz("ayar_ses_motor", "sunucu"); yaz("ayar_ses_motor_isim", "ahmet"); }
      else if (v === "sunucu-emel") { yaz("ayar_ses_motor", "sunucu"); yaz("ayar_ses_motor_isim", "emel"); }
      else { yaz("ayar_ses_motor", "tarayici"); }
    });
  }

  // ── Test paneli yardımcıları ──────────────────────────
  let audioCtx = null;
  let masterGain = null;
  let suspendTimer = null;
  function audioHazirla() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      masterGain = audioCtx.createGain();
      masterGain.gain.value = 0.18 * (parseFloat(sesSeviyesi.value) || 1.0);
      masterGain.connect(audioCtx.destination);
    }
    if (audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
    return audioCtx;
  }
  function audioSus() {
    if (suspendTimer) clearTimeout(suspendTimer);
    suspendTimer = setTimeout(() => {
      try { if (audioCtx && audioCtx.state === "running") audioCtx.suspend(); } catch (e) {}
    }, 800);
  }
  function bipCal() {
    try {
      const ctx = audioHazirla();
      const simdi = ctx.currentTime;
      [0, 0.28].forEach((gec, i) => {
        const osc = ctx.createOscillator();
        const env = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = 700 + i * 200;
        env.gain.setValueAtTime(0, simdi + gec);
        env.gain.linearRampToValueAtTime(1.0, simdi + gec + 0.04);
        env.gain.linearRampToValueAtTime(0.7, simdi + gec + 0.12);
        env.gain.linearRampToValueAtTime(0, simdi + gec + 0.22);
        osc.connect(env).connect(masterGain);
        osc.start(simdi + gec);
        osc.stop(simdi + gec + 0.24);
      });
      audioSus();
    } catch (e) {}
  }

  function konusTarayici(metin) {
    return new Promise((resolve) => {
      try { speechSynthesis.cancel(); } catch (e) {}
      const u = new SpeechSynthesisUtterance(metin);
      u.lang = "tr-TR";
      u.rate = parseFloat(sesHiz.value) || 1.0;
      u.volume = parseFloat(sesSeviyesi.value) || 1.0;
      const ad = sesSecim.value;
      if (ad) {
        const v = speechSynthesis.getVoices().find(x => x.name === ad);
        if (v) u.voice = v;
      }
      u.onend = () => resolve();
      u.onerror = () => resolve();
      setTimeout(() => speechSynthesis.speak(u), 100);
    });
  }

  function konusSunucu(metin, isim) {
    return new Promise((resolve) => {
      const hiz = parseFloat(sesHiz.value) || 1.0;
      const url = "/api/tts?ses=" + encodeURIComponent(isim || "ahmet")
                + "&hiz=" + encodeURIComponent(hiz)
                + "&metin=" + encodeURIComponent(metin);
      const dusus = () => konusTarayici(metin).then(resolve);
      try {
        fetch(url, { cache: "force-cache" })
          .then((r) => { if (!r.ok) throw new Error("http " + r.status); return r.blob(); })
          .then((blob) => {
            const objUrl = URL.createObjectURL(blob);
            const audio = new Audio();
            audio.preload = "auto";
            audio.src = objUrl;
            audio.volume = parseFloat(sesSeviyesi.value) || 1.0;
            const temizle = () => { try { URL.revokeObjectURL(objUrl); } catch(e){} };
            audio.onended = () => { temizle(); resolve(); };
            audio.onerror = () => { temizle(); dusus(); };
            audio.oncanplaythrough = () => { audio.play().catch(() => { temizle(); dusus(); }); };
            setTimeout(() => { if (audio.paused) audio.play().catch(() => { temizle(); dusus(); }); }, 800);
          })
          .catch(() => dusus());
      } catch (e) { dusus(); }
    });
  }

  function konus(metin) {
    const motor = oku("ayar_ses_motor", "tarayici");
    if (motor === "sunucu") {
      const isim = oku("ayar_ses_motor_isim", "ahmet");
      return konusSunucu(metin, isim);
    }
    return konusTarayici(metin);
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
    await new Promise(r => setTimeout(r, 1000));
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
        await new Promise(rr => setTimeout(rr, 1000));
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
    ["ayar_min","ayar_konum_aktif","ayar_lat","ayar_lon","ayar_yaricap","ayar_ses_hiz","ayar_ses_seviyesi","ayar_ses_adi","ayar_ses_motor","ayar_ses_motor_isim"]
      .forEach(k => localStorage.removeItem(k));
    location.reload();
  });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
})();
