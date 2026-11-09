// ==UserScript==
// @name         Player page → PES Face AI
// @namespace    https://github.com/FabianZettl/pes-photo-to-face
// @version      0.7
// @description  One click on a player page that YOU opened (FMInside, Transfermarkt, SoFIFA): sends name, club, birth date and photo to your local PES Face AI tool.
// @match        https://fminside.net/players/*
// @match        https://www.fminside.net/players/*
// @match        https://www.transfermarkt.com/*/profil/spieler/*
// @match        https://www.transfermarkt.de/*/profil/spieler/*
// @match        https://www.transfermarkt.co.uk/*/profil/spieler/*
// @match        https://sofifa.com/player/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      127.0.0.1
// @connect      *
// ==/UserScript==
// Runs only when you press the button on a page you opened yourself. It does not crawl, search or follow links.
// The photo is handed to your local tool, which computes the face from it and drops it (it is never stored or shared,
// and never used for training). Selectors are best guesses for these sites: when something is not found the toast says
// what, and the console shows what the script saw.

(function () {
  "use strict";
  const SERVER = "http://localhost:8000";
  const $ = (s, r = document) => r.querySelector(s);
  const text = (el) => (el ? el.textContent.trim() : "");

  function site() {
    if (window.__PFA_SITE) return window.__PFA_SITE;
    const h = location.hostname, p = location.pathname;
    if (/(^|\.)fminside\.net$/.test(h) && /^\/players\/\d+-[^/]+\/\d+-[^/]+\/?$/.test(p)) return "fminside";
    if (/(^|\.)transfermarkt\./.test(h) && /\/profil\/spieler\/\d+/.test(p)) return "transfermarkt";
    if (/(^|\.)sofifa\.com$/.test(h) && /^\/player\/\d+/.test(p)) return "sofifa";
    return null;
  }

  const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
  const iso = (y, m, d) => `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  function findDob(t) {   // first birth-date-looking text: 08/11/2002, 8.11.2002, Nov 8, 2002, 8 November 2002, 2002-11-08
    let m;
    if ((m = /\b(\d{4})-(\d{2})-(\d{2})\b/.exec(t))) return iso(m[1], m[2], m[3]);
    if ((m = /\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b/.exec(t))) return iso(m[3], m[2], m[1]);
    if ((m = /\b([A-Za-z]{3})[a-z]* (\d{1,2}),? (\d{4})\b/.exec(t)) && MONTHS[m[1].toLowerCase()]) return iso(m[3], MONTHS[m[1].toLowerCase()], m[2]);
    if ((m = /\b(\d{1,2}) ([A-Za-z]{3})[a-z]* (\d{4})\b/.exec(t)) && MONTHS[m[2].toLowerCase()]) return iso(m[3], MONTHS[m[2].toLowerCase()], m[1]);
    return "";
  }

  function jsonLd() {   // schema.org Person / athlete blocks, if the page has them
    const out = [];
    document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
      try {
        const walk = (o) => { if (Array.isArray(o)) o.forEach(walk); else if (o && typeof o === "object") { out.push(o); if (o["@graph"]) walk(o["@graph"]); } };
        walk(JSON.parse(s.textContent));
      } catch (e) { /* not JSON */ }
    });
    return out.find((o) => /Person|Athlete/i.test([].concat(o["@type"] || []).join(" "))) || {};
  }

  // FMInside also carries the Football Manager attributes
  const FM_ATTRS = ["Corners", "Crossing", "Dribbling", "Finishing", "First Touch", "Free Kick Taking", "Heading", "Long Shots",
    "Long Throws", "Marking", "Passing", "Penalty Taking", "Tackling", "Technique", "Aggression", "Anticipation", "Bravery",
    "Composure", "Concentration", "Decisions", "Determination", "Flair", "Leadership", "Off the Ball", "Positioning",
    "Teamwork", "Vision", "Work Rate", "Acceleration", "Agility", "Balance", "Jumping Reach", "Natural Fitness", "Pace",
    "Stamina", "Strength", "Aerial Reach", "Command of Area", "Communication", "Eccentricity", "Handling", "Kicking",
    "One on Ones", "Punching", "Reflexes", "Rushing Out", "Throwing"];

  function scrapeStats() {
    const stats = {};
    document.querySelectorAll("table tr").forEach((tr) => {
      const n = $("[data-player-stat-name]", tr), v = $(".stat", tr);
      if (n && v) stats[n.getAttribute("data-player-stat-name")] = text(v);
    });
    if (Object.keys(stats).length) return stats;
    const want = new Set(FM_ATTRS.map((a) => a.toLowerCase()));
    const num = (t) => { const m = /(^|\D)(\d{1,2})(\D|$)/.exec(t); return m && +m[2] >= 1 && +m[2] <= 20 ? m[2] : null; };
    document.querySelectorAll("body *").forEach((el) => {
      if (el.children.length) return;
      const name = text(el);
      if (!want.has(name.toLowerCase())) return;
      const cands = [el.nextElementSibling && text(el.nextElementSibling), el.parentElement && text(el.parentElement).replace(name, ""),
        el.parentElement && el.parentElement.nextElementSibling && text(el.parentElement.nextElementSibling)];
      for (const c of cands) { const v = c && num(c); if (v) { if (!(name in stats)) stats[name] = v; break; } }
    });
    return stats;
  }

  function scrape() {
    const s = site(), ld = jsonLd();
    const og = (p) => $(`meta[property="${p}"]`)?.content || "";
    const ldName = typeof ld.name === "string" ? ld.name : "";
    const ldImg = typeof ld.image === "string" ? ld.image : ld.image && ld.image.url || "";
    const ldTeam = ld.memberOf && ld.memberOf.name || ld.affiliation && ld.affiliation.name || "";
    let d = { source: s, name: ldName, team: ldTeam, nationality: "", dob: ld.birthDate ? findDob(String(ld.birthDate)) : "", stats: {}, url: location.href, imageUrl: ldImg || og("og:image") };
    if (s === "fminside") {
      const info = {};
      document.querySelectorAll("div#player_info div.column li").forEach((li) => { const k = text($("span.key", li)).replace(":", ""); if (k) info[k] = text($("span.value", li)); });
      const find = (re) => Object.entries(info).find(([k]) => re.test(k))?.[1] || "";
      d.name = text($(".player-hero-copy h1")) || text($("h1")) || d.name;
      d.team = find(/^(club|team)$/i) || d.team;
      d.nationality = text($('.player-hero-eyebrow a.player-hero-eyebrow-link[href^="/players/"] span'));
      d.dob = findDob(find(/birth|born|dob/i)) || d.dob;
      d.stats = scrapeStats();
    } else if (s === "transfermarkt") {
      const head = $(".data-header") || document.body;
      d.name = text($("h1.data-header__headline-wrapper")).replace(/^#\d+\s*/, "").replace(/\s+/g, " ") || d.name || og("og:title").split(" - ")[0];
      d.team = text($(".data-header__club a")) || d.team;
      d.dob = findDob(text($('[itemprop="birthDate"]'))) || d.dob || findDob(text(head));
      d.imageUrl = $("img.data-header__profile-image")?.src || d.imageUrl;
    } else if (s === "sofifa") {
      const head = $(".profile") || $("main") || document.body;
      d.name = d.name || text($(".profile h1")) || og("og:title").split(" - ")[0];
      d.team = d.team || text($('a[href^="/team/"]'));
      d.dob = d.dob || findDob(text(head));
      d.imageUrl = $(".profile img")?.src || d.imageUrl;
    }
    d.name = (d.name || "").replace(/\s*\(.*\)\s*$/, "").trim() || d.name;
    return d;
  }

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

  // The list thumbnails are small (SoFIFA 120 px): try the larger variants of the same image first, then the original.
  function imageUrls(u) {
    const out = [];
    if (/sofifa\.net\/.*_\d+\.png/.test(u)) for (const w of [360, 240, 180]) out.push(u.replace(/_\d+\.png/, `_${w}.png`));
    if (/transfermarkt[^/]*\/portrait\/(header|medium|small)\//.test(u)) out.push(u.replace(/\/portrait\/(header|medium|small)\//, "/portrait/big/"));
    out.push(u);
    return out;
  }

  const gm = (opts) => new Promise((res, rej) => GM_xmlhttpRequest({ ...opts, onload: res, onerror: () => rej(new Error("Netzwerkfehler")), ontimeout: () => rej(new Error("Zeitüberschreitung")) }));

  async function send() {
    const d = scrape();
    console.log("[PES Face AI] gefunden:", { ...d, stats: Object.keys(d.stats).length + " Werte" });
    if (!d.name) return toast("Name nicht gefunden (Seitenlayout geändert?). Siehe Konsole.", true);
    if (!d.dob) console.warn("[PES Face AI] kein Geburtsdatum gefunden: der Abgleich läuft nur über Name und Verein");
    try {
      let image = null, note = "";
      if (d.imageUrl) {
        // fetch the photo the way the page itself does (page as referrer); if the image server refuses, the data is
        // sent anyway and the photo can be dropped into the tool by hand
        let im = null;
        for (const u of imageUrls(d.imageUrl)) {
          im = await gm({ method: "GET", url: u, responseType: "blob", timeout: 20000,
            headers: { Referer: location.href, Accept: "image/avif,image/webp,image/*,*/*;q=0.8" } });
          console.log("[PES Face AI] Bild:", u, "Status", im.status, "Typ", im.response && im.response.type, "Größe", im.response && im.response.size);
          if (im.status === 200 && im.response && im.response.size >= 500) break;
        }
        if (im.status === 200 && im.response && im.response.size >= 500) {
          image = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(im.response); });
        } else note = ` Foto-Download abgelehnt (Status ${im.status}): bitte das Foto im Tool-Tab "Eingang" von Hand ablegen.`;
      } else note = ' Kein Foto auf der Seite gefunden: bitte im Tool-Tab "Eingang" von Hand ablegen (siehe Konsole).';
      const r = await gm({ method: "POST", url: SERVER + "/api/fm/import", headers: { "Content-Type": "application/json" },
        data: JSON.stringify({ ...d, image }), timeout: 60000 });
      if (r.status !== 200) return toast("Tool meldet: " + (JSON.parse(r.responseText).detail || r.status), true);
      const j = JSON.parse(r.responseText), best = j.best[0];
      if (j.auto) return toast(`Gesicht für ${best.name} berechnet (exakter Treffer: Name und Geburtsdatum) und abgeglichen.`);
      if (d.source === "fminside" && !Object.keys(d.stats).length) note += " Keine Werte gefunden (siehe Konsole).";
      toast((best ? `Gesendet. Bester Treffer: ${best.name} (${Math.round(best.score * 100)} %). Bestätige im Tab "Eingang".` : "Gesendet, aber kein Treffer in der Spielerliste. Wähle im Tool von Hand.") + note, !!note);
    } catch (e) {
      toast("Konnte das Tool nicht erreichen (läuft es auf " + SERVER + "?): " + e.message, true);
    }
  }

  if (window.__PFA_TEST) { window.__pfaScrape = scrape; return; }
  if (!site()) return;
  const b = document.createElement("button");
  b.textContent = "→ PES Face AI";
  b.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:99999;padding:10px 16px;border:0;border-radius:10px;background:#2563eb;color:#fff;font:600 14px system-ui;cursor:pointer;box-shadow:0 4px 16px #0005";
  b.onclick = send;
  document.body.append(b);
})();
