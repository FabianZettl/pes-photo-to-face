import contextlib, io, os, tempfile, time
from pathlib import Path

from fastapi import Body, FastAPI, Request, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import model
from . import newworld as nw
from .encoder import photo_warnings, predict_all

app = FastAPI()

# The server has no login, so a web page you happen to visit must not be able to drive it:
# state-changing requests are accepted only from our own UI (or without an Origin header, e.g. curl and
# userscript managers), and /api/fm/* additionally from fminside.net pages.
OWN = {"http://localhost:8000", "http://127.0.0.1:8000"}
FM = {"https://fminside.net", "https://www.fminside.net"}


@app.middleware("http")
async def origin_guard(request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
        ok = OWN | (FM if request.url.path.startswith("/api/fm/") else set())
        port = os.environ.get("PESFACE_PORT")
        if port:
            ok |= {f"http://localhost:{port}", f"http://127.0.0.1:{port}"}
        if origin not in ok:
            return JSONResponse({"detail": "Origin nicht erlaubt"}, status_code=403)
    return await call_next(request)
WEB = Path(__file__).resolve().parent.parent / "web"


def _predict(upload: UploadFile):
    with tempfile.NamedTemporaryFile(suffix=Path(upload.filename or "x.jpg").suffix) as t:
        t.write(upload.file.read()); t.flush()
        try:
            _predict.warnings = photo_warnings(t.name)
            return predict_all(t.name)
        except ValueError as e:
            raise HTTPException(422, str(e))


@app.post("/api/predict")
def predict(photo: UploadFile = File(...)):
    vals = _predict(photo)
    return JSONResponse({"values": vals, "ranges": {**model.ranges(), **model.HAIR_RANGES}, "warnings": _predict.warnings})


@app.post("/api/export.csv")
def export(photo: UploadFile = File(...), player_id: str = Form("0")):
    buf = io.StringIO()
    model.to_csv([(player_id, _predict(photo))], buf)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="face_{player_id}.csv"'})


@app.post("/api/queue")
def queue(photo: UploadFile = File(...), player_id: str = Form(...), hair_style: str = Form(""),
          hair_length: str = Form(""), hair_curl: str = Form(""), hair_front: str = Form(""),
          hair_parting: str = Form(""), hair_hairline: str = Form(""), hair_forehead: str = Form(""), hair_back: str = Form("")):
    if not player_id.isdigit():
        raise HTTPException(422, "Spieler-ID fehlt oder ist keine Zahl")
    vals = _predict(photo)
    for k, v in (("HairStyle", hair_style), ("HairLength", hair_length), ("HairCurl", hair_curl), ("HairFront", hair_front),
                 ("HairParting", hair_parting), ("HairHairline", hair_hairline), ("HairForehead", hair_forehead), ("HairBack", hair_back)):
        if v.isdigit():   # empty = leave the template's hair alone
            vals[k] = int(v)
    n = model.queue(player_id, vals)
    return {"queued": player_id, "in_queue": n, "file": str(model.QUEUE)}


TRAIN = model.TRAIN_DIR


@app.get("/api/truth")
def truth(player_id: int):
    """The player's current in-game values (latest appearance dump) for the training tab."""
    from . import hairdata
    try:
        d = hairdata.latest_dump()
        t = hairdata.decode(d)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if player_id not in t:
        raise HTTPException(404, "Spieler hat keinen Datensatz im Dump")
    import json
    lay = json.load(open(model.DATA / "layout.json"))
    return {"values": t[player_id], "ranges": {n: [v["lo"], v["hi"]] for n, v in lay.items()},
            "dump": time.strftime("%d.%m. %H:%M", time.localtime(os.path.getmtime(d)))}


@app.get("/api/train/list")
def train_list():
    TRAIN.mkdir(exist_ok=True)
    return sorted(f.stem for f in TRAIN.iterdir() if f.stem.isdigit())


@app.post("/api/train/photo")
def train_photo(photo: UploadFile = File(...), player_id: str = Form(...)):
    from .encoder import encode, photo_warnings
    if not player_id.isdigit():
        raise HTTPException(422, "Spieler-ID fehlt")
    TRAIN.mkdir(exist_ok=True)
    for old in TRAIN.glob(player_id + ".*"):
        old.unlink()
    ext = Path(photo.filename or "x.jpg").suffix.lower() or ".jpg"
    dest = TRAIN / (player_id + ext)
    dest.write_bytes(photo.file.read())
    try:
        warn = photo_warnings(str(dest))
    except ValueError as e:
        dest.unlink()
        raise HTTPException(422, str(e))
    return {"saved": dest.name, "count": len(train_list()), "warnings": warn}


@app.post("/api/train/run")
def train_run():
    """Retrain the face model (with the training photos added) and the hair model; returns what it printed."""
    from . import hairmodel
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        try:
            r = model.evaluate()
            model.train()
            print("Gesicht: mittlere Verbesserung gegenüber dem Durchschnitt (Kreuzvalidierung) "
                  f"{100 * sum(1 - e / b for e, b in r.values()) / len(r):.1f} %")
            from . import hair
            hair.calibrate_colour(str(TRAIN))
            hairmodel.train(str(TRAIN))
        except Exception as e:   # shown in the UI instead of a bare 500
            print("Fehler:", e)
    return {"log": log.getvalue()}


@app.get("/api/hair/list")
def hair_list():
    from . import hairmodel
    return hairmodel.counts()


@app.post("/api/hair/photo")
def hair_photo(photo: UploadFile = File(...), style: int = Form(...), length: int = Form(...), curl: int = Form(...),
               front: str = Form(""), parting: str = Form(""), hairline: str = Form(""), forehead: str = Form(""), back: str = Form("")):
    """A hand-labelled hair photo: the user says how he would build the hair in the game."""
    import json, uuid
    from . import hairmodel
    from .encoder import encode, photo_warnings
    hairmodel.HAIR_DIR.mkdir(exist_ok=True)
    name = "h_" + uuid.uuid4().hex[:8]
    dest = hairmodel.HAIR_DIR / (name + (Path(photo.filename or "x.jpg").suffix.lower() or ".jpg"))
    dest.write_bytes(photo.file.read())
    try:
        warn = photo_warnings(str(dest))
    except ValueError as e:
        dest.unlink()
        raise HTTPException(422, str(e))
    labels = json.loads(hairmodel.LABELS.read_text()) if hairmodel.LABELS.exists() else {}
    labels[name] = {"HairStyle": style, "HairLength": length, "HairCurl": curl}
    for k, v in (("HairFront", front), ("HairParting", parting), ("HairHairline", hairline), ("HairForehead", forehead), ("HairBack", back)):
        if v.isdigit():
            labels[name][k] = int(v)
    hairmodel.LABELS.write_text(json.dumps(labels))
    return {**hairmodel.counts(), "warnings": warn}


BULK = {"running": False, "total": 0, "done": 0, "items": [], "queue": ""}
IMG = {".jpg", ".jpeg", ".png", ".webp", ""}


def _bulk_run(files):
    import threading  # noqa: F401  (thread started by the caller)
    from .encoder import photo_warnings
    for f in files:
        item = {"file": f.name, "id": f.stem, "status": "ok", "msg": ""}
        try:
            if not f.stem.isdigit():
                raise ValueError("Dateiname ist keine Spieler-ID")
            hit = model.search_players(f.stem, limit=1)
            item["name"] = hit[0]["name"] if hit and hit[0]["id"] == int(f.stem) else ""
            if not item["name"]:
                item["msg"] = "ID nicht in der Spielerliste; "
            warn = photo_warnings(str(f))
            model.queue(f.stem, predict_all(str(f)))
            item["msg"] += " · ".join(warn)
            if warn:
                item["status"] = "warn"
        except Exception as e:   # one bad photo must not stop the run
            item["status"], item["msg"] = "skip", str(e)
        BULK["items"].append(item)
        BULK["done"] += 1
    BULK["running"] = False


@app.post("/api/bulk/start")
def bulk_start(folder: str = Form(...)):
    import threading
    if BULK["running"]:
        raise HTTPException(409, "Es läuft schon ein Durchlauf")
    d = Path(folder.strip()).expanduser()
    if not d.is_dir():
        raise HTTPException(422, f"Ordner nicht gefunden: {d}")
    files = sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMG)
    if not files:
        raise HTTPException(422, "Keine Fotos im Ordner")
    BULK.update(running=True, total=len(files), done=0, items=[], queue=str(model.QUEUE))
    threading.Thread(target=_bulk_run, args=(files,), daemon=True).start()
    return {"total": len(files)}


@app.get("/api/bulk/status")
def bulk_status():
    return BULK


INBOX = {}   # id -> item; photos stay in memory only and are dropped as soon as the item is handled
MAX_IMG = 8 * 1024 * 1024


def _to_jpeg(raw):
    """Whatever the site or the user hands over (jpg, png, webp, gif, avif, ...) -> plain JPEG bytes."""
    from PIL import Image
    if len(raw) > MAX_IMG:
        raise HTTPException(413, "Bild zu groß")
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=95)
        return buf.getvalue()
    except Exception:
        raise HTTPException(422, f"Die Daten sind kein lesbares Bild ({len(raw)} Bytes, Anfang: {raw[:24]!r})")


DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%d/%m/%Y", "%d.%m.%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y")
AUTO = {"on": True}   # compute the face right away when the match is exact (birth date equal, name nearly equal)


def _iso(dob):
    import datetime
    for f in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(dob.strip().split(" (")[0], f).date().isoformat()
        except ValueError:
            continue
    return None


def _cands(name, team, dob):
    """Name/club candidates from the player list, plus new-world players whose birth date equals the one on the page.
    A candidate is `exact` when birth date is equal and the name is nearly equal (>= 0.9)."""
    import difflib
    cands = model.match_players(name, team)
    iso = _iso(dob)
    if iso and nw.available():
        for p in nw.players():
            if p["born"] == iso and set(model._tokens(name)) & set(model._tokens(p["name"])):
                r = difflib.SequenceMatcher(None, " ".join(model._tokens(name)), " ".join(model._tokens(p["name"]))).ratio()
                cands = [c for c in cands if c["id"] != p["id"]]
                cands.insert(0, {"id": p["id"], "name": p["name"], "teams": [p["club"]], "has_face": True, "score": 1.0,
                                 "exact": r >= 0.9})
    return cands[:5]


def _accept(it, player_id):
    """Face from the item's photo (+ converted FM stats) for this player. New-world players: values go to the NewLife-id
    store (Sync); the photo itself is never kept. Returns what the UI shows."""
    import json
    warn, n = [], None
    nwp = nw.by_game_id(player_id) if nw.available() and str(player_id).isdigit() else None
    if it["image"] is not None:
        with tempfile.NamedTemporaryFile(suffix=it["ext"]) as t:
            t.write(it["image"]); t.flush()
            try:
                warn = photo_warnings(t.name)
                if nwp and not nwp["rendered"]:
                    nw.compute(nwp["nl"], path=t.name)
                    warn.append("Neue-Welt-Spieler: Gesicht gespeichert, im Tab New World „Mit Build abgleichen“ drücken")
                    n = 0
                else:
                    n = model.queue(player_id, predict_all(t.name))
            except ValueError as e:
                raise HTTPException(422, str(e))
    else:
        warn = ["Kein Foto: nur die Werte wurden übernommen, kein Gesicht"]
    if it.get("stats"):
        f = model.QUEUE.parent / "fm_stats.json"   # raw FM attributes per player id, for a later stat converter
        store = json.loads(f.read_text()) if f.exists() else {}
        store[str(player_id)] = {k: it[k] for k in ("name", "team", "nationality", "dob", "stats", "url")}
        f.write_text(json.dumps(store, ensure_ascii=False))
    from . import stats
    conv = stats.convert(it["stats"]) if it.get("stats") else {}
    if conv:   # kept permanently: the game rebuilds its player table at every start
        stats.queue(model.QUEUE.parent / "faceai_stats.csv", player_id, conv)
    return {"queued": str(player_id), "in_queue": n, "warnings": warn, "stats": len(conv)}


@app.post("/api/fm/import")
async def fm_import(request: Request):
    """From the userscript: one player page opened by the user in his own browser."""
    import base64, re, uuid
    d = await request.json()
    name, team = str(d.get("name", "")).strip(), str(d.get("team", "")).strip()
    if not name:
        raise HTTPException(422, "Name fehlt")
    raw, kind = None, ".jpg"
    if d.get("image"):   # optional: when the browser could not fetch the photo it is attached later by hand
        m = re.match(r"data:[^,]*;base64,(.*)", d["image"], re.S)
        if not m:
            raise HTTPException(422, "Bild: data-URL erwartet")
        raw = _to_jpeg(base64.b64decode(m.group(1)))
    iid = uuid.uuid4().hex[:8]
    INBOX[iid] = {"id": iid, "name": name, "team": team, "nationality": str(d.get("nationality", "")),
                  "dob": str(d.get("dob", "")), "stats": d.get("stats") or {}, "url": str(d.get("url", "")),
                  "source": str(d.get("source", "fminside")),
                  "ext": kind, "image": raw, "cands": _cands(name, team, str(d.get("dob", "")))}
    it = INBOX[iid]
    best = it["cands"][0] if it["cands"] else None
    if AUTO["on"] and best and best.get("exact") and raw is not None:
        nwp = nw.by_game_id(best["id"]) if nw.available() else None
        if nwp and not nwp["rendered"]:   # only new-world players are built without asking
            try:
                _accept(it, best["id"])
                del INBOX[iid]
                return {"ok": True, "id": iid, "auto": True, "best": [best]}
            except HTTPException as e:
                it["note"] = str(e.detail)   # stays in the inbox with the reason
    return {"ok": True, "id": iid, "best": it["cands"][:1]}


@app.get("/api/fm/inbox")
def fm_inbox():
    return [{**{k: v for k, v in it.items() if k != "image"}, "has_image": it["image"] is not None} for it in INBOX.values()]


@app.post("/api/fm/attach")
def fm_attach(item_id: str = Form(...), photo: UploadFile = File(...)):
    """Photo supplied by hand for an item whose browser download failed."""
    it = INBOX.get(item_id)
    if not it:
        raise HTTPException(404, "Eintrag nicht gefunden")
    it["image"] = _to_jpeg(photo.file.read())
    return {"ok": True}


@app.get("/api/fm/photo/{iid}")
def fm_photo(iid: str):
    it = INBOX.get(iid)
    if not it or it["image"] is None:
        raise HTTPException(404)
    return Response(it["image"], media_type="image/jpeg")


@app.post("/api/fm/accept")
def fm_accept(item_id: str = Form(...), player_id: str = Form(...)):
    """Confirm the match: face from the photo, queue it, keep the stats, drop the photo."""
    it = INBOX.get(item_id)
    if not it or not player_id.isdigit():
        raise HTTPException(422, "Eintrag oder Spieler-ID ungültig")
    out = _accept(it, player_id)
    del INBOX[item_id]
    return out


@app.get("/api/fm/settings")
def fm_settings():
    return AUTO


@app.post("/api/fm/settings")
def fm_set_settings(auto: str = Form(...)):
    AUTO["on"] = auto == "1"
    return AUTO


@app.post("/api/fm/discard")
def fm_discard(item_id: str = Form(...)):
    INBOX.pop(item_id, None)
    return {"ok": True}


# ---------------------------------------------------------------- New World (players of a Mod Studio build)
NWP = {"running": False, "total": 0, "done": 0, "errors": []}


def _nw_need():
    if not nw.available():
        raise HTTPException(404, f"{nw.PLAYERIDS} nicht gefunden: SIDER_DIR (SiderAddons) setzen und in Mod Studio einmal bauen")


@app.get("/api/newworld/summary")
def nw_summary():
    _nw_need()
    return nw.summary()


@app.get("/api/newworld/list")
def nw_list(q: str = "", state: str = "", limit: int = 100, club: str = ""):
    _nw_need()
    rows, total = nw.listing(q, state, limit, club)
    return {"rows": rows, "total": total}


@app.post("/api/newworld/refresh")
def nw_refresh():
    _nw_need()
    nw.players(refresh=True)
    return nw.summary()


@app.get("/api/newworld/photo/{nl}")
def nw_photo(nl: str):
    f = nw.photo_file(nl)
    if not f:
        raise HTTPException(404)
    return FileResponse(f)


@app.post("/api/newworld/photo")
def nw_set_photo(nl: str = Form(...), photo: UploadFile = File(...)):
    _nw_need()
    nw.save_photo(nl, _to_jpeg(photo.file.read()))
    return {"ok": True}


def _nw_run(nls):
    for nl in nls:
        try:
            nw.compute(nl)
        except Exception as e:   # one bad photo must not stop the run
            NWP["errors"].append(f"{nl}: {e}")
        NWP["done"] += 1
    NWP["running"] = False


@app.post("/api/newworld/compute")
def nw_compute(nl: str = Form("")):
    """One player (nl given) or every player that has a photo but no face yet."""
    import threading
    _nw_need()
    if NWP["running"]:
        raise HTTPException(409, "Es läuft schon eine Berechnung")
    st = nw._store()
    todo = [nl] if nl else [p["nl"] for p in nw.players() if not p["rendered"] and nw.photo_file(p["nl"]) and p["nl"] not in st]
    if not todo:
        raise HTTPException(422, "Nichts zu berechnen: kein Spieler mit Foto ohne Gesicht")
    NWP.update(running=True, total=len(todo), done=0, errors=[])
    threading.Thread(target=_nw_run, args=(todo,), daemon=True).start()
    return {"total": len(todo)}


@app.get("/api/newworld/progress")
def nw_progress():
    return NWP


@app.post("/api/newworld/sync")
def nw_sync():
    _nw_need()
    return nw.sync()


@app.post("/api/newworld/commons/check")
def nw_commons_check(nls: list = Body(..., embed=True)):
    """Metadata only, no image: for which of these players does Wikimedia Commons offer a free portrait?"""
    from . import commons
    _nw_need()
    want = {str(x) for x in nls[:100]}
    try:
        return commons.check([p for p in nw.players() if p["nl"] in want])
    except Exception as e:
        raise HTTPException(502, f"Wikimedia nicht erreichbar: {e}")


@app.post("/api/newworld/commons/fetch")
def nw_commons_fetch(nl: str = Form(...)):
    """Download the photo of ONE player after the user confirmed the preview."""
    from . import commons
    _nw_need()
    p = next((p for p in nw.players() if p["nl"] == nl), None)
    if not p:
        raise HTTPException(404, "Spieler nicht gefunden")
    try:
        return commons.fetch(nl, p["name"], p["born"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"Wikimedia nicht erreichbar: {e}")


@app.get("/api/newworld/clubs")
def nw_clubs():
    _nw_need()
    return nw.clubs()


@app.post("/api/newworld/team/check")
def nw_team_check(club: str = Form(...)):
    """Who of this club needs a face, who already has a photo, for whom Commons offers a free one. Metadata only."""
    from . import commons
    _nw_need()
    todo = nw.needs_build(club)
    nophoto = [p for p in todo if not nw.photo_file(p["nl"])]
    try:
        offers = commons.check(nophoto, min_ratio=0.9) if nophoto else {}
    except Exception as e:
        raise HTTPException(502, f"Wikimedia nicht erreichbar: {e}")
    return {"club": club, "need": len(todo), "have_photo": len(todo) - len(nophoto), "offers": len(offers),
            "players": [{"name": p["name"], "born": p["born"], "overall": p["overall"],
                         "status": "Foto vorhanden" if nw.photo_file(p["nl"]) else
                         f"Commons: {offers[p['nl']]['author']} · {offers[p['nl']]['license']}" if p["nl"] in offers else "kein freies Foto gefunden"}
                        for p in sorted(todo, key=lambda p: -(p["overall"] or 0))]}


TEAM = {"running": False, "phase": "", "club": "", "total": 0, "done": 0, "items": [], "errors": [], "result": None}


def _team_run(club):
    from . import commons
    try:
        todo = nw.needs_build(club)
        TEAM.update(total=len(todo), done=0, items=[{"name": p["name"], "status": "wartet"} for p in todo], errors=[])
        row = {p["nl"]: i for i, p in enumerate(todo)}
        nophoto = [p for p in todo if not nw.photo_file(p["nl"])]
        TEAM["phase"] = "Suche freie Fotos auf Wikimedia Commons"
        offers = commons.check(nophoto, width=1000, min_ratio=0.9) if nophoto else {}
        for p in todo:
            i = row[p["nl"]]
            try:
                if p["nl"] in offers:
                    TEAM["phase"] = f"Lade Foto: {p['name']}"
                    commons.save_candidate(p["nl"], offers[p["nl"]])
                    TEAM["items"][i]["status"] = "Foto geladen"
                elif nw.photo_file(p["nl"]):
                    TEAM["items"][i]["status"] = "Foto vorhanden"
                else:
                    TEAM["items"][i]["status"] = "kein freies Foto gefunden"
                    continue
                TEAM["phase"] = f"Berechne Gesicht: {p['name']}"
                nw.compute(p["nl"])
                TEAM["items"][i]["status"] += " · Gesicht berechnet"
            except Exception as e:   # one player must not stop the team
                TEAM["items"][i]["status"] = f"Fehler: {e}"
                TEAM["errors"].append(f"{p['name']}: {e}")
            TEAM["done"] += 1
        TEAM["done"] = TEAM["total"]
        TEAM["phase"] = "Gleiche mit dem Build ab"
        TEAM["result"] = nw.sync()
        TEAM["phase"] = "Fertig"
    except Exception as e:
        TEAM["errors"].append(str(e))
        TEAM["phase"] = "Abgebrochen"
    TEAM["running"] = False


@app.post("/api/newworld/team/build")
def nw_team_build(club: str = Form(...)):
    """One club on request: photos for those who have none (free Commons portraits, strict match), faces, then Sync."""
    import threading
    _nw_need()
    if TEAM["running"] or NWP["running"]:
        raise HTTPException(409, "Es läuft schon eine Berechnung")
    if not nw.needs_build(club):
        raise HTTPException(422, "Dieses Team braucht keinen Build")
    TEAM.update(running=True, club=club, phase="Start", result=None)
    threading.Thread(target=_team_run, args=(club,), daemon=True).start()
    return {"ok": True}


@app.get("/api/newworld/team/progress")
def nw_team_progress():
    return TEAM


@app.get("/api/players")
def players(q: str = "", face_only: bool = False, team: str = ""):
    return model.search_players(q, face_only, team)


@app.get("/api/teams")
def teams():
    return model.team_names()


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
