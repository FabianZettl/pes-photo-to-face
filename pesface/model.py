"""Embedding (128-d Facenet) -> PES face slider values. Ridge per slider; rounded and clipped to the slider range."""
import csv, json, os, pickle
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

DATA = Path(__file__).resolve().parent.parent / "data"
MODEL_PATH = DATA / "model.pkl"


def load_dataset():
    for f in ("encodings.json", "data-cleaned.csv"):
        if not (DATA / f).exists():
            raise SystemExit(f"data/{f} fehlt: python -m pesface fetch-base-data (siehe README)")
    enc = json.load(open(DATA / "encodings.json"))
    with open(DATA / "data-cleaned.csv", newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        cols = set(rd.fieldnames)
        rows = {r["Id"]: r for r in rd}
    lay = json.load(open(DATA / "layout.json"))
    names = [n for n in lay if n in cols and not n.startswith("Hair")]   # sliders the CSV has labels for
    ranges = {n: [lay[n]["lo"], lay[n]["hi"]] for n in names}
    ids = [i for i in enc if i in rows]
    X = np.array([enc[i] for i in ids], dtype=float)
    Y = np.array([[float(rows[i][n]) for n in names] for i in ids])
    ex = extra_samples(names)
    if ex:
        X = np.vstack([X, ex[0]]); Y = np.vstack([Y, ex[1]]); ids = ids + ex[2]
    return ids, X, Y, names, ranges


def _fit(X, Y):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    return {"mu": mu, "sd": sd, "ridge": Ridge(alpha=30).fit((X - mu) / sd, Y)}


def _raw(m, X):
    return m["ridge"].predict((np.atleast_2d(X) - m["mu"]) / m["sd"])


def evaluate(n_splits=5):
    """5-fold CV MAE per slider vs. always-predict-the-mean baseline."""
    _, X, Y, names, _ = load_dataset()
    err, base = np.zeros(Y.shape), np.zeros(Y.shape)
    for tr, te in KFold(n_splits, shuffle=True, random_state=0).split(X):
        m = _fit(X[tr], Y[tr])
        err[te] = np.abs(_raw(m, X[te]) - Y[te])
        base[te] = np.abs(Y[tr].mean(0) - Y[te])
    return {n: (err[:, i].mean(), base[:, i].mean()) for i, n in enumerate(names)}


def train():
    _, X, Y, names, ranges = load_dataset()
    pickle.dump({"m": _fit(X, Y), "names": names, "ranges": ranges}, open(MODEL_PATH, "wb"))


def predict(embedding):
    b = pickle.load(open(MODEL_PATH, "rb"))
    raw = _raw(b["m"], embedding)[0]
    return {n: int(np.clip(round(v), *b["ranges"][n])) for n, v in zip(b["names"], raw)}


def to_csv(rows, path_or_file):
    """rows: [(player_id, {slider: value})] -> CSV with the same column names as the PES edit-data export."""
    names = list(rows[0][1])
    w = csv.writer(path_or_file)
    w.writerow(["Id", *names])
    for pid, vals in rows:
        w.writerow([pid, *vals.values()])


def ranges():
    return pickle.load(open(MODEL_PATH, "rb"))["ranges"]


QUEUE = Path(os.environ.get("FACEAI_QUEUE") or Path(os.environ.get("FACEAI_DIR", DATA.parent / "faceai")) / "faceai.csv")


def queue(player_id, vals, path=QUEUE):
    """Add or replace the row of player_id in the sider import queue (rows the game imports are removed by faceai.lua)."""
    rows, old = {}, []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            old = rd.fieldnames or []
            rows = {r["Id"]: r for r in rd if r.get("Id")}
    rows[str(player_id)] = {"Id": str(player_id), **{k: str(v) for k, v in vals.items()}}
    cols = ["Id", *[c for c in [*old, *vals] if c != "Id"]]
    cols = list(dict.fromkeys(cols))
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols, restval="", extrasaction="ignore", lineterminator="\r\n")
        w.writeheader(); w.writerows(rows.values())
    tmp.replace(path)
    return len(rows)


PLAYERS = DATA / "players.json"


def _teams_of_players(pesdb):
    """pesdb = folder with Team.bin / PlayerAssignment.bin -> {player_id: [team names]}.
    Both are 16-byte header + zlib. Team.bin: 1532-byte records, name at +0, team id u32 360 bytes before the name;
    PlayerAssignment.bin: 16-byte records (index, player id, team id, ?)."""
    import struct, zlib
    rd = lambda f: zlib.decompress(open(Path(pesdb) / f, "rb").read()[16:])
    t, S, base = rd("Team.bin"), 1532, 368
    name = {}
    for k in range((len(t) - base) // S):
        o = base + k * S
        name[struct.unpack_from("<I", t, o - 360)[0]] = t[o:o + 64].split(b"\0")[0].decode("utf-8", "replace").strip()
    a, by = rd("PlayerAssignment.bin"), {}
    for o in range(0, len(a), 16):
        _, pid, tid, _ = struct.unpack_from("<4I", a, o)
        if tid in name:
            by.setdefault(pid, []).append(name[tid])
    return by


def build_players(players_dump, appearance_dump, pesdb):
    """players_dump.bin (PlayerDump F7, 0x17C bytes/player: id +0x30, name +0x38) -> data/players.json.
    has_face = the player has a record in the appearance table (appearance_mem_NN.bin, F8), i.e. can be imported."""
    b = np.fromfile(players_dump, np.uint8).reshape(-1, 0x17C)
    a = np.fromfile(appearance_dump, np.uint8).reshape(-1, 72)
    have = set(a[:, :4].copy().view("<u4").ravel().tolist())
    teams = _teams_of_players(pesdb)
    out = []
    for r in b:
        pid = int(r[0x30:0x34].view("<u4")[0])
        name = bytes(r[0x38:0x38 + 0x30]).split(b"\0")[0].decode("utf-8", "replace")
        if name:
            out.append({"id": pid, "name": name, "has_face": pid in have, "teams": teams.get(pid, [])})
    json.dump(out, open(PLAYERS, "w", encoding="utf-8"), ensure_ascii=False)
    return len(out)


def _fold(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def search_players(q, only_with_face=False, team="", limit=50):
    global _players
    if not PLAYERS.exists():
        return []
    if "_players" not in globals():
        _players = [dict(p, k=_fold(p["name"])) for p in json.load(open(PLAYERS, encoding="utf-8"))]
    words = _fold(q).split()
    team = team.lower()
    hits = (p for p in _players if (p["has_face"] or not only_with_face)
            and (not team or any(team == t.lower() for t in p["teams"]))
            and all(w in p["k"] or w == str(p["id"]) for w in words))
    return [{k: v for k, v in p.items() if k != "k"} for _, p in zip(range(limit), hits)]


def team_names():
    search_players("", limit=0)
    return sorted({t for p in _players for t in p["teams"]})


HAIR_RANGES = {"HairStyle": [0, 7], "HairLength": [0, 5], "HairCurl": [0, 6],
               "HairColourR": [0, 63], "HairColourG": [0, 63], "HairColourB": [0, 63],
               "HairFront": [1, 3], "HairParting": [1, 6], "HairHairline": [1, 3], "HairForehead": [1, 3], "HairBack": [1, 4], "HairColourType": [0, 7]}


TRAIN_DIR = DATA.parent / "training"


def extra_samples(names):
    """Training photos (training/<player id>.<ext>) with the current in-game values of that player as labels
    -> (embeddings, labels, ids), or None. Embeddings are cached in data/train_feats.pkl."""
    if not TRAIN_DIR.exists():
        return None
    from .hairdata import decode, latest_dump
    try:
        truth = decode()
    except FileNotFoundError:
        return None
    cache_f = DATA / "train_feats.pkl"
    cache = pickle.load(open(cache_f, "rb")) if cache_f.exists() else {}
    from .encoder import encode
    X, Y, ids = [], [], []
    for f in sorted(TRAIN_DIR.iterdir()):
        if not f.stem.isdigit() or int(f.stem) not in truth:
            continue
        key = (f.name, f.stat().st_mtime)
        if key not in cache:
            try:
                cache[key] = encode(str(f))
            except ValueError:
                continue
        t = truth[int(f.stem)]
        if all(n in t for n in names):
            X.append(cache[key]); Y.append([float(t[n]) for n in names]); ids.append(f.stem)
    pickle.dump(cache, open(cache_f, "wb"))
    return (np.array(X, dtype=float), np.array(Y), ids) if X else None
