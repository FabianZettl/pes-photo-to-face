"""New-world players of an FL Mod Studio build: who they are, who still has the generic pack face, whose face we computed.

Inputs (all written by Mod Studio, read-only here):
  <SiderAddons>/livecpk/_FL26MyWorld/fl26playerids.json   game id, name, club, birth date, NewLife id of every new player
  <SiderAddons>/modules/fl26world.txt                      `newfaces` lines = players that get the generic pack face
  NewLife release zips (NEWLIFE_DIR, optional)             ratings and club names
Faces are stored under the NewLife id, because Mod Studio hands out the game id at Build ("first free id") and it can
change; `sync()` writes the rows with the CURRENT game ids plus a fingerprint of fl26playerids.json that the Sider module
checks, so a face can never land on the wrong player after a rebuild."""
import csv
import glob
import io
import json
import os
import re
import struct
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACEAI_DIR = Path(os.environ.get("FACEAI_DIR", ROOT / "faceai"))
SIDER = Path(os.environ.get("SIDER_DIR") or FACEAI_DIR.parent.parent)
WORLD = Path(os.environ.get("WORLD_DIR") or SIDER / "livecpk" / "_FL26MyWorld")
PLAYERIDS = WORLD / "fl26playerids.json"
WORLDTXT = SIDER / "modules" / "fl26world.txt"
STORE = FACEAI_DIR / "newworld_faces.json"     # nl id -> {"values": {...}, "name": ..., "game_id": ...}
OUT = FACEAI_DIR / "faceai_newworld.csv"       # rows with the current game ids, applied by faceai.lua
SIG = FACEAI_DIR / "faceai_world.sig"          # line 1: path of fl26playerids.json relative to SiderAddons, line 2: fingerprint
PHOTOS = Path(os.environ.get("NEWWORLD_PHOTOS") or ROOT / "newworld_photos")

OUTFIELD = ["Offensive Awareness", "Ball Control", "Dribbling", "Tight Possession", "Low Pass", "Lofted Pass", "Finishing",
            "Heading", "Speed", "Acceleration", "Kicking Power", "Jump", "Physical Contact", "Balance", "Stamina",
            "Defensive Awareness", "Ball Winning", "Aggression"]
GK = ["GK Awareness", "GK Catching", "GK Clearing", "GK Reflexes", "GK Reach"]
_cache = {}


def fingerprint(data):
    """Same function in faceai.lua: h = (h * 31 + byte) mod 2^32 over the whole file."""
    h = 0
    for b in data:
        h = (h * 31 + b) & 0xFFFFFFFF
    return h


def _newlife_dirs():
    d = os.environ.get("NEWLIFE_DIR")
    return [Path(d).expanduser()] if d else [Path(p) for p in glob.glob(str(Path("~/Downloads/NewLife*").expanduser()))]


def _newlife(nls):
    """{nl id: overall} and {newlife club id: club name} from the release zips (empty when there are none)."""
    over, clubs = {}, {}
    zips = [z for d in _newlife_dirs() for z in d.rglob("*.zip")]
    for z in zips:
        try:
            zf = zipfile.ZipFile(z)
            if "clubs.csv" in zf.namelist():
                for r in csv.DictReader(io.TextIOWrapper(zf.open("clubs.csv"), encoding="utf-8")):
                    clubs[r["newlife_id"]] = r["name"]
            if "players.csv" in zf.namelist():
                for r in csv.DictReader(io.TextIOWrapper(zf.open("players.csv"), encoding="utf-8")):
                    if r["newlife_id"] in nls:
                        cols = GK if r["Registered Position"] == "GK" else OUTFIELD
                        vals = [int(r[c]) for c in cols if r.get(c, "").isdigit()]
                        over[r["newlife_id"]] = round(sum(vals) / len(vals)) if vals else 0
        except (zipfile.BadZipFile, KeyError):
            continue
    return over, clubs


def _team_names():
    t = zlib.decompress((WORLD / "common" / "etc" / "pesdb" / "Team.bin").read_bytes()[16:])
    S, base, out = 1532, 368, {}
    for k in range((len(t) - base) // S):
        o = base + k * S
        out[str(struct.unpack_from("<I", t, o - 360)[0])] = t[o:o + 64].split(b"\0")[0].decode("utf-8", "replace").strip()
    return out


def _newfaces():
    ids = set()
    if WORLDTXT.exists():
        for line in WORLDTXT.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*newfaces3?d?\s+(.*)", line)
            if m:
                for a, b in re.findall(r"(\d+)-?(\d*)", m.group(1)):
                    ids.update(range(int(a), int(b or a) + 1))
    return ids


def real_faces():
    """Player ids that already have a rendered face model in some face pack: <livecpk root>/Asset/model/character/face/real/<id>/.
    Such a player needs no slider face. All roots under SiderAddons/livecpk are scanned (or the dirs in FACE_DIRS, ';'-separated)."""
    dirs = [Path(d) for d in os.environ["FACE_DIRS"].split(";")] if os.environ.get("FACE_DIRS") else \
        [Path(x) for x in glob.glob(str(SIDER / "livecpk" / "*" / "Asset" / "model" / "character" / "face" / "real"))]
    ids = set()
    for d in dirs:
        if d.is_dir():
            ids.update(int(e.name) for e in os.scandir(d) if e.is_dir() and e.name.isdigit())
    return ids


def available():
    return PLAYERIDS.exists()


def players(refresh=False):
    """All new-world players, one dict each. Cached; refresh=True re-reads the Mod Studio files."""
    if "p" in _cache and not refresh:
        return _cache["p"]
    d = json.loads(PLAYERIDS.read_text(encoding="utf-8"))
    nls = {p["nl"] for m in d["people"].values() for p in m.values()}
    over, nl_clubs = _newlife(nls)
    teams = _team_names()
    newfaces = _newfaces()
    rendered = real_faces()
    out = []
    for club, m in d["clubs"].items():
        label = teams.get(club) or nl_clubs.get(str(d["club_nl"].get(club, ""))) or club
        for k, gid in m.items():
            p = d["people"][club][k]
            out.append({"nl": str(p["nl"]), "id": gid, "name": d["names"][club][k], "club": label, "born": p["born"],
                        "overall": over.get(str(p["nl"])), "generic": gid in newfaces,
                        "rendered": gid in rendered})
    _cache["p"] = out
    _cache["by_gid"] = {p["id"]: p for p in out}
    return out


def by_game_id(gid):
    players()
    return _cache["by_gid"].get(int(gid))


def _store():
    return json.loads(STORE.read_text()) if STORE.exists() else {}


def photo_file(nl):
    return next(iter(PHOTOS.glob(f"{nl}.*")), None) if PHOTOS.exists() else None


def save_photo(nl, jpeg_bytes):
    PHOTOS.mkdir(exist_ok=True)
    for old in PHOTOS.glob(f"{nl}.*"):
        old.unlink()
    (PHOTOS / f"{nl}.jpg").write_bytes(jpeg_bytes)


def _credit(nl):
    f = PHOTOS / "credits.json"
    return json.loads(f.read_text()).get(nl) if f.exists() else None


def listing(q="", state="", limit=200, club=""):
    """Rows for the UI, strongest players first. state: '' | 'nophoto' | 'photo' | 'done'."""
    st = _store()
    from .model import _fold
    q = _fold(q).split()   # accent-insensitive: 'aydogdu' finds 'Aydoğdu'
    rows = []
    for p in players():
        if club and p["club"] != club:
            continue
        has_photo = photo_file(p["nl"]) is not None
        s = "rendered" if p["rendered"] else "done" if p["nl"] in st else "photo" if has_photo else "nophoto"
        if not state and s == "rendered":
            continue   # hidden unless asked for: they need nothing
        if state and s != state:
            continue
        hay = _fold(f'{p["name"]} {p["club"]} {p["born"]}')
        if all(w in hay for w in q):
            rows.append({**p, "state": s, "credit": _credit(p["nl"])})
    rows.sort(key=lambda r: -(r["overall"] or 0))
    return rows[:limit], len(rows)


def clubs():
    """[{club, total, need}] sorted by name; need = players without a rendered face and without a computed face."""
    st = _store()
    out = {}
    for p in players():
        c = out.setdefault(p["club"], {"club": p["club"], "total": 0, "need": 0})
        c["total"] += 1
        c["need"] += (not p["rendered"]) and p["nl"] not in st
    return sorted(out.values(), key=lambda c: c["club"].lower())


def needs_build(club):
    """Players of this club that still need a face built."""
    st = _store()
    return [p for p in players() if p["club"] == club and not p["rendered"] and p["nl"] not in st]


def summary():
    st = _store()
    ps = players()
    todo = [p for p in ps if not p["rendered"]]
    return {"all": len(ps), "rendered": len(ps) - len(todo), "total": len(todo),
            "photo": sum(photo_file(p["nl"]) is not None for p in todo), "done": sum(p["nl"] in st for p in todo),
            "synced": _sync_ok()}


def compute(nl, path=None):
    """Photo of this player -> face values, stored under his NewLife id. path: a photo that is NOT kept (browser hand-off);
    without it the stored photo of the player is used."""
    from .encoder import predict_all
    f = path or photo_file(nl)
    if not f:
        raise ValueError("kein Foto")
    p = next(p for p in players() if p["nl"] == nl)
    if p["rendered"]:
        raise ValueError("hat schon ein gerendertes Gesicht")
    vals = predict_all(str(f))
    st = _store()
    st[nl] = {"values": vals, "name": p["name"], "game_id": p["id"]}
    FACEAI_DIR.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(st))


def _store_state(st):
    """What the last Sync has to contain: which faces, for which game ids."""
    return str(fingerprint(json.dumps(sorted((k, v.get("game_id")) for k, v in st.items())).encode()))


def _sync_ok():
    """True when the last Sync belongs to this build AND already contains every stored face."""
    if not (SIG.exists() and PLAYERIDS.exists()):
        return False
    lines = SIG.read_text().split()
    return len(lines) >= 3 and lines[1] == str(fingerprint(PLAYERIDS.read_bytes())) and lines[2] == _store_state(_store())


def sync():
    """Write faceai_newworld.csv with the CURRENT game ids and the fingerprint of the build the ids belong to.
    Returns {"written": n, "moved": [..], "gone": n}."""
    st = _store()
    cur = {p["nl"]: p for p in players(refresh=True)}
    rows, moved, gone = [], [], 0
    for nl, f in st.items():
        p = cur.get(nl)
        if not p:
            gone += 1
            continue
        if p["rendered"]:   # a rendered face appeared since: the slider face would not be used
            continue
        if p["id"] != f.get("game_id"):
            moved.append(f"{p['name']}: {f.get('game_id')} -> {p['id']}")
            f["game_id"] = p["id"]
        rows.append({"Id": p["id"], **f["values"]})
    cols = ["Id"] + [c for c in dict.fromkeys(c for r in rows for c in r) if c != "Id"]
    FACEAI_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, cols, restval="", extrasaction="ignore", lineterminator="\r\n")
        w.writeheader(); w.writerows(rows)
    STORE.write_text(json.dumps(st))
    SIG.write_text(f"{PLAYERIDS.relative_to(SIDER).as_posix()}\n{fingerprint(PLAYERIDS.read_bytes())}\n{_store_state(st)}\n")
    return {"written": len(rows), "moved": moved, "gone": gone}
