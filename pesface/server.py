import contextlib, io, os, tempfile, time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import model
from .encoder import photo_warnings, predict_all

app = FastAPI()
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


@app.get("/api/players")
def players(q: str = "", face_only: bool = False, team: str = ""):
    return model.search_players(q, face_only, team)


@app.get("/api/teams")
def teams():
    return model.team_names()


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
