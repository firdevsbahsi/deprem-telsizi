// AFAD Deprem PWA — istemci mantığı
// baslat.bat ile aynı davranır:
//  - Sayfa açılış zamanını "başlangıç" olarak sabitler
//  - Sadece o saatten SONRAKI depremleri sırayla sesli okur
//  - Format: "Afet ve Acil Durum Başkanlığı verilerine göre saat HH:MM
//    sularında YER ve çevresinde X.X büyüklüğünde yer sarsıntısı meydana
//    gelmiştir."
(function () {
  "use strict";

  const govde = document.body;
  const OZEL = govde.dataset.ozel === "1";

  function ayarOku(k, vars) {
    try {
      const v = localStorage.getItem(k);
      if (v === null) return vars;
      return JSON.parse(v);
    } catch (e) { return vars; }
  }
  const A = {
    min: ayarOku("ayar_min", 2.0),
    konumAktif: ayarOku("ayar_konum_aktif", false),
    lat: ayarOku("ayar_lat", null),
    lon: ayarOku("ayar_lon", null),
    yaricap: ayarOku("ayar_yaricap", 500),
    sesHiz: ayarOku("ayar_ses_hiz", 1.0),
    sesAdi: ayarOku("ayar_ses_adi", ""),
  };

  const ESIK = OZEL ? parseFloat(A.min) : parseFloat(govde.dataset.esik || "0");
  const liste = document.getElementById("liste");
  const durum = document.getElementById("durum");
  const sayac = document.getElementById("sayac");
  const btnSes = document.getElementById("btn-ses");
  const btnTest = document.getElementById("btn-test");
  const baslikEl = document.getElementById("baslik");

  if (OZEL && baslikEl) baslikEl.textContent = `Özel — M${ESIK.toFixed(1)}+`;

  const YENILEME_MS = 20000; // 20 sn (sunucu zaten arka planda çekiyor)
  const SAKLA_KEY = "deprem_ses_aktif_" + (OZEL ? "ozel" : "m" + ESIK);

  // Sayfa açılış zamanı (TR saati cinsinden epoch ms)
  // 15 dk öncesinden başlat: sayfa açıldığında son birkaç dakikadaki
  // yeni depremleri de yakalasın (kullanıcı tam o sırada açtıysa kaçırmasın).
  const BASLANGIC = Date.now() - 15 * 60 * 1000;
  const BASLANGIC_STR = new Date(BASLANGIC).toLocaleTimeString("tr-TR");

  let sesAktif = localStorage.getItem(SAKLA_KEY) !== "0";
  let okunanIdler = new Set(); // bu oturumda okuduklarımız
  let okumaKuyrugu = [];
  let okuniyor = false;
  let okundularLog = []; // "Ŝu deprem okundu" göstergesi için (en son 10 id)

  // ── Service Worker ─────────────────────────────────────
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  // ── Ses toggle ─────────────────────────────────────────
  function sesGuncelle() {
    btnSes.textContent = sesAktif ? "🔔" : "🔕";
    btnSes.classList.toggle("kapali", !sesAktif);
  }
  sesGuncelle();
  btnSes.addEventListener("click", () => {
    sesAktif = !sesAktif;
    localStorage.setItem(SAKLA_KEY, sesAktif ? "1" : "0");
    sesGuncelle();
    if (sesAktif) {
      // İzni almak için kullanıcı etkileşimi sırasında bir kez konuş
      try {
        const u = new SpeechSynthesisUtterance("Sesli uyarı aktif.");
        u.lang = "tr-TR";
        speechSynthesis.speak(u);
      } catch (e) {}
    } else {
      try { speechSynthesis.cancel(); } catch (e) {}
      okumaKuyrugu = [];
      okuniyor = false;
    }
  });

  // Test butonu: en son depremi anında oku (her şey çalışıyor mu kontrol)
  if (btnTest) {
    btnTest.addEventListener("click", async () => {
      btnTest.disabled = true;
      bipCal();
      if ("vibrate" in navigator) navigator.vibrate([200, 100, 200]);
      try {
        const r = await fetch(apiUrl(), { cache: "no-store" });
        const v = await r.json();
        if (v.depremler && v.depremler.length > 0) {
          await new Promise((res) => setTimeout(res, 500));
          await konus("Test. " + anonsMetni(v.depremler[0]));
        } else {
          await konus("Test. Bu eşikte deprem yok.");
        }
      } catch (e) {
        await konus("Test. Bağlantı hatası.");
      }
      btnTest.disabled = false;
    });
  }

  // ── Bip + TTS ──────────────────────────────────────────
  let audioCtx = null;
  let masterGain = null;
  let suspendTimer = null;
  function audioHazirla() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      masterGain = audioCtx.createGain();
      masterGain.gain.value = 0.18;
      masterGain.connect(audioCtx.destination);
    }
    if (audioCtx.state === "suspended") {
      audioCtx.resume().catch(() => {});
    }
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

  function trSesSec() {
    const sesler = speechSynthesis.getVoices();
    if (A.sesAdi) {
      const tam = sesler.find((v) => v.name === A.sesAdi);
      if (tam) return tam;
    }
    return sesler.find((v) => /tr/i.test(v.lang)) || null;
  }

  function konus(metin) {
    return new Promise((resolve) => {
      if (!("speechSynthesis" in window)) return resolve();
      const u = new SpeechSynthesisUtterance(metin);
      u.lang = "tr-TR";
      const v = trSesSec();
      if (v) u.voice = v;
      u.rate = parseFloat(A.sesHiz) || 1.0;
      u.pitch = 1.0;
      u.onend = () => resolve();
      u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }

  // ── Kuyruk işleyici (depremleri tek tek sırayla okur) ───
  async function kuyruguIsle() {
    if (okuniyor) return;
    okuniyor = true;
    while (okumaKuyrugu.length > 0) {
      const dep = okumaKuyrugu.shift();
      // Bir önceki konuşmayı garanti durdur (TTS örtüşme paraziti)
      try { speechSynthesis.cancel(); } catch (e) {}
      // "Şu an okunuyor" rozeti
      const kart = liste.querySelector(`.deprem[data-id="${cssKacis(dep.id)}"]`);
      if (kart) kart.classList.add("okunuyor");
      bipCal();
      if ("vibrate" in navigator) navigator.vibrate([200, 100, 200]);
      // Bip tamamen bitsin (ADSR ~250ms + tampon)
      await new Promise((r) => setTimeout(r, 900));
      const metin = anonsMetni(dep);
      await konus(metin);
      // Okundu olarak işaretle
      okundularLog.push(dep.id);
      if (okundularLog.length > 50) okundularLog.shift();
      if (kart) {
        kart.classList.remove("okunuyor");
        kart.classList.add("okundu");
      }
      durum.textContent = `✓ Şu okundu: M${dep.buyukluk.toFixed(1)} ${dep.yer.substring(0, 30)}`;
      await new Promise((r) => setTimeout(r, 1000));
    }
    okuniyor = false;
  }

  function cssKacis(s) {
    return String(s).replace(/["\\\]\[]/g, "\\$&");
  }

  // ── Yardımcılar ────────────────────────────────────────
  function tarihParse(tarihStr) {
    // "YYYY-MM-DD HH:MM:SS" → Date (TR saati varsayımıyla +03:00)
    try {
      const t = String(tarihStr).replace(" ", "T") + "+03:00";
      const dt = new Date(t);
      if (isNaN(dt)) return null;
      return dt;
    } catch (e) { return null; }
  }

  function saatStr(tarihStr) {
    const dt = tarihParse(tarihStr);
    if (!dt) return String(tarihStr);
    return dt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  }

  function zamanFormat(tarihStr) {
    const dt = tarihParse(tarihStr);
    if (!dt) return tarihStr;
    const bugun = new Date();
    const ayni = dt.getFullYear() === bugun.getFullYear()
              && dt.getMonth() === bugun.getMonth()
              && dt.getDate() === bugun.getDate();
    if (ayni) {
      return dt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
    return dt.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function anonsMetni(d) {
    // sesli_mesaj_olustur ile aynı format
    const kurum = d.kaynak === "Kandilli"
      ? "Kandilli Rasathanesi verilerine göre"
      : "Afet ve Acil Durum Başkanlığı verilerine göre";
    return `${kurum} saat ${saatStr(d.tarih)} sularında ${d.yer} ve çevresinde ${d.buyukluk.toFixed(1)} büyüklüğünde yer sarsıntısı meydana gelmiştir.`;
  }

  function html_kacis(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function depremKart(d, yeni) {
    const buyuklukTam = Math.floor(d.buyukluk);
    const okunduMu = okundularLog.includes(d.id);
    const rozet = okunduMu ? '<span class="okundu-rozet" title="Sesli okundu">🔊</span>' : "";
    return `
      <div class="deprem ${yeni ? "yeni" : ""} ${okunduMu ? "okundu" : ""}" data-buyukluk="${buyuklukTam}" data-id="${html_kacis(d.id)}">
        <div class="mag">${d.buyukluk.toFixed(1)}</div>
        <div class="bilgi">
          <div class="yer">${html_kacis(d.yer)} ${rozet}</div>
          <div class="detay">
            Derinlik: ${html_kacis(d.derinlik)} km · ${html_kacis(d.enlem)}, ${html_kacis(d.boylam)}
            <span class="kaynak-rozet">${html_kacis(d.kaynak)}</span>
          </div>
        </div>
        <div class="zaman">${zamanFormat(d.tarih)}</div>
      </div>
    `;
  }

  // ── Yenileme döngüsü ───────────────────────────────────
  function apiUrl() {
    const p = new URLSearchParams({ min: String(ESIK) });
    if (OZEL && A.konumAktif && A.lat != null && A.lon != null) {
      p.set("lat", A.lat);
      p.set("lon", A.lon);
      p.set("r", A.yaricap);
    }
    return "/api/depremler?" + p.toString();
  }

  async function yenile() {
    durum.textContent = "Yenileniyor…";
    try {
      const yanit = await fetch(apiUrl(), { cache: "no-store" });
      const veri = await yanit.json();
      if (!veri.ok) throw new Error("api hata");

      // Listeyi çiz
      if (veri.depremler.length === 0) {
        liste.innerHTML = `<div class="bos">Son 24 saat içinde M${ESIK}.0+ deprem yok.<br><small>Başlangıç: ${BASLANGIC_STR} — sadece bu saatten sonrakiler okunur.</small></div>`;
      } else {
        liste.innerHTML = veri.depremler
          .map((d) => {
            const dt = tarihParse(d.tarih);
            const yeni = dt && dt.getTime() > BASLANGIC;
            return depremKart(d, yeni);
          })
          .join("");
      }

      // Sadece BAŞLANGIÇTAN sonraki + henüz okunmamış olanları al
      const okunacaklar = [];
      for (const d of veri.depremler) {
        const dt = tarihParse(d.tarih);
        if (!dt) continue;
        if (dt.getTime() <= BASLANGIC) continue;
        if (okunanIdler.has(d.id)) continue;
        okunacaklar.push(d);
      }

      // Eskiden yeniye oku (baslat.bat: yeniler.reverse())
      okunacaklar.sort((a, b) => tarihParse(a.tarih) - tarihParse(b.tarih));

      if (okunacaklar.length > 0 && sesAktif) {
        for (const d of okunacaklar) {
          okunanIdler.add(d.id);
          okumaKuyrugu.push(d);
        }
        kuyruguIsle();
      } else {
        // Ses kapalıyken bile "okundu" say (geri açınca eski olanları okumasın)
        for (const d of okunacaklar) okunanIdler.add(d.id);
      }

      durum.textContent = `✓ ${veri.guncelleme} · ${veri.toplam} deprem · başl. ${BASLANGIC_STR}`;
      sayac.textContent = OZEL ? `M${ESIK.toFixed(1)}+` : `M${ESIK}.0+`;
    } catch (e) {
      durum.textContent = "⚠ Bağlantı hatası";
    }
  }

  // İlk yükleme: var olan depremleri okuma — sadece çiz
  // (Mantığı yenile() içindeki BASLANGIC filtresi zaten sağlıyor)
  yenile();
  setInterval(yenile, YENILEME_MS);

  // Sayfaya geri dönünce hemen yenile
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) yenile();
  });

  // Sesler async yüklenir — ilk seferde voices boş olabilir
  if ("speechSynthesis" in window) {
    speechSynthesis.onvoiceschanged = () => {};
  }
})();
