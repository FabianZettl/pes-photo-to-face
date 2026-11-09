// ==UserScript==
// @name         FMInside → PES Face AI
// @namespace    https://github.com/FabianZettl/pes-photo-to-face
// @version      0.1
// @description  One click on a player page that YOU opened: sends name, club, stats and photo to your local PES Face AI tool.
// @match        https://fminside.net/players/*
// @match        https://www.fminside.net/players/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      127.0.0.1
// @connect      *
// ==/UserScript==
// Runs only when you press the button on a page you opened yourself. It does not crawl, search or follow links.
// The photo is handed to your local tool, which keeps it in memory until you confirm the match, then drops it.
// Selectors below are best guesses for the FMInside layout: if the site changes, the toast says what was not found.

(function () {
  "use strict";
  const SERVER = "http://localhost:8000";
  if (!/^\/players\/\d+-[^/]+\/\d+-[^/]+\/?$/.test(location.pathname)) return;

  const $ = (s, r = document) => r.querySelector(s);
  const text = (el) => (el ? el.textContent.trim() : "");

  function toast(msg, bad) {
    let t = $("#pfa-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "pfa-toast";
      t.style.cssText = "position:fixed;right:16px;bottom:64px;z-index:99999;max-width:340px;padding:10px 14px;border-radius:10px;font:14px system-ui;color:#fff;box-shadow:0 4px 16px #0005";
      document.body.append(t);
    }
    t.style.background = bad ? "#b91c1c" : "#15803d";
    t.textContent = msg;
    clearTimeout(t._h);
    t._h = setTimeout(() => t.remove(), 9000);
  }

  function info() {
    const out = {};
    document.querySelectorAll("div#player_info div.column li").forEach((li) => {
      const k = text($("span.key", li)).replace(":", "");
      if (k) out[k] = text($("span.value", li));
    });
    return out;
  }

  function scrape() {
    const name = text($(".player-hero-copy h1")) || text($("h1"));
    const i = info();
    const find = (re) => Object.entries(i).find(([k]) => re.test(k))?.[1] || "";
    const stats = {};
    document.querySelectorAll("table tr").forEach((tr) => {
      const n = $("[data-player-stat-name]", tr), v = $(".stat", tr);
      if (n && v) stats[n.getAttribute("data-player-stat-name")] = text(v);
    });
    const img = $('meta[property="og:image"]')?.content || $(".player-hero img")?.src || "";
    return {
      name,
      team: find(/^(club|team)$/i),
      nationality: text($('.player-hero-eyebrow a.player-hero-eyebrow-link[href^="/players/"] span')),
      dob: find(/birth|born|dob/i),
      stats, url: location.href, imageUrl: img,
    };
  }

  const gm = (opts) => new Promise((res, rej) => GM_xmlhttpRequest({ ...opts, onload: res, onerror: () => rej(new Error("Netzwerkfehler")), ontimeout: () => rej(new Error("Zeitüberschreitung")) }));

  async function send() {
    const d = scrape();
    console.log("[PES Face AI] gefunden:", { ...d, stats: Object.keys(d.stats).length + " Werte" });
    if (!d.name) return toast("Name nicht gefunden (Seitenlayout geändert?). Siehe Konsole.", true);
    if (!d.imageUrl) return toast("Foto nicht gefunden (Seitenlayout geändert?). Siehe Konsole.", true);
    try {
      const im = await gm({ method: "GET", url: d.imageUrl, responseType: "blob", timeout: 20000 });
      const dataUrl = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(im.response); });
      const r = await gm({ method: "POST", url: SERVER + "/api/fm/import", headers: { "Content-Type": "application/json" },
        data: JSON.stringify({ ...d, image: dataUrl }), timeout: 30000 });
      if (r.status !== 200) return toast("Tool meldet: " + (JSON.parse(r.responseText).detail || r.status), true);
      const best = JSON.parse(r.responseText).best[0];
      toast(best ? `Gesendet. Bester Treffer: ${best.name} (${Math.round(best.score * 100)} %). Bestätige im Tab "FM".` : "Gesendet, aber kein Treffer in der Spielerliste. Wähle im Tool von Hand.");
    } catch (e) {
      toast("Konnte das Tool nicht erreichen (läuft es auf " + SERVER + "?): " + e.message, true);
    }
  }

  const b = document.createElement("button");
  b.textContent = "→ PES Face AI";
  b.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:99999;padding:10px 16px;border:0;border-radius:10px;background:#2563eb;color:#fff;font:600 14px system-ui;cursor:pointer;box-shadow:0 4px 16px #0005";
  b.onclick = send;
  document.body.append(b);
})();
