"""Portraits from Wikimedia Commons for new-world players, fetched ON REQUEST only.

Match: Wikidata footballer with the same birth date and a similar name -> its image (P18) on Commons. Only freely licensed
files are offered (CC0, public domain, CC BY, CC BY-SA) and only from 400 px up. Checking costs metadata queries; an image is
downloaded only when the user confirms one player. Author, licence and source are kept next to the photo (credits.json)."""
import difflib
import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from . import newworld as nw

UA = "PES-Face-AI/0.1 (https://github.com/FabianZettl/pes-photo-to-face; on-request portraits)"
MIN_SIDE = 400
CREDITS = nw.PHOTOS / "credits.json"
_last = [0.0]


def _get(url, accept=None):
    wait = 1.0 - (time.time() - _last[0])   # at most one request per second
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    h = {"User-Agent": UA}
    if accept:
        h["Accept"] = accept
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=80)


def _fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c)).replace("-", " ").replace(".", "")


def license_ok(name):
    n = (name or "").lower()
    return "cc0" in n or "public domain" in n or n.startswith("pd") or bool(re.match(r"cc[ -]by([ -]sa)?([ -]\d|\s|$)", n))


def clean_author(raw):
    return html.unescape(re.sub(r"<[^>]+>", "", raw or "")).strip() or "unbekannt"


def _wikidata(dates):
    """{birth date: [(label, commons file name or None)]} for footballers born on these dates."""
    out = {}
    for i in range(0, len(dates), 40):
        vals = " ".join(f'"{d}T00:00:00Z"^^xsd:dateTime' for d in dates[i:i + 40])
        q = (f'SELECT ?pLabel ?dob ?img WHERE {{ VALUES ?dob {{ {vals} }} ?p wdt:P569 ?dob ; wdt:P106 wd:Q937857 . '
             f'OPTIONAL {{ ?p wdt:P18 ?img }} SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}')
        r = json.load(_get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q), "application/sparql-results+json"))
        for b in r["results"]["bindings"]:
            img = b.get("img", {}).get("value")
            out.setdefault(b["dob"]["value"][:10], []).append(
                (b["pLabel"]["value"], urllib.parse.unquote(img.rsplit("/", 1)[-1]) if img else None))
    return out


def _imageinfo(files, width):
    """{file name: {w, h, license, author, thumb, page}} from Commons."""
    out = {}
    for i in range(0, len(files), 40):
        titles = "|".join("File:" + f for f in files[i:i + 40])
        url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=size|url|extmetadata"
               f"&iiextmetadatafilter=LicenseShortName|Artist&iiurlwidth={width}&titles=" + urllib.parse.quote(titles))
        for pg in json.load(_get(url))["query"]["pages"].values():
            ii = (pg.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            out[pg["title"][5:].replace(" ", "_")] = {
                "w": ii.get("width", 0), "h": ii.get("height", 0), "thumb": ii.get("thumburl"), "page": ii.get("descriptionurl"),
                "license": em.get("LicenseShortName", {}).get("value", "?"), "author": clean_author(em.get("Artist", {}).get("value"))}
    return out


def check(players, width=240):
    """players: list of {nl, name, born}. -> {nl: candidate} for the ones with an offered (free, big enough) photo.
    Metadata only: no image is downloaded."""
    wd = _wikidata(sorted({p["born"] for p in players}))
    pick = {}
    for p in players:
        best = (0.0, None)
        for label, img in wd.get(p["born"], []):
            r = difflib.SequenceMatcher(None, _fold(p["name"]), _fold(label)).ratio()
            if img and r > best[0]:
                best = (r, img)
        if best[0] >= 0.85:
            pick[p["nl"]] = best[1].replace(" ", "_")
    info = _imageinfo(sorted(set(pick.values())), width) if pick else {}
    out = {}
    for nl, f in pick.items():
        i = info.get(f)
        if i and min(i["w"], i["h"]) >= MIN_SIDE and license_ok(i["license"]):
            out[nl] = {"file": f, **i}
    return out


def fetch(nl, name, born):
    """Download the offered photo of ONE player (called when the user confirms) and keep its credit."""
    cand = check([{"nl": nl, "name": name, "born": born}], width=1000).get(nl)
    if not cand:
        raise ValueError("kein freies Commons-Foto für diesen Spieler")
    raw = _get(cand["thumb"]).read()
    from .server import _to_jpeg
    nw.save_photo(nl, _to_jpeg(raw))
    credits = json.loads(CREDITS.read_text()) if CREDITS.exists() else {}
    credits[nl] = {k: cand[k] for k in ("author", "license", "page", "file")}
    CREDITS.write_text(json.dumps(credits, ensure_ascii=False))
    return credits[nl]


def credit(nl):
    c = json.loads(CREDITS.read_text()) if CREDITS.exists() else {}
    return c.get(nl)
