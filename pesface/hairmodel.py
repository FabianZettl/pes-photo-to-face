"""Learned hair model: image features of a head -> style / length / curl and the front/side/back options.

Three kinds of training samples, all as features + labels:
  training/<player id>.<ext>      photo of a player, labels = his in-game values (appearance dump)
  training_hair/<n>.<ext>         photo you labelled by hand in the Haare tab (labels.json)
  training_hair/embedded.json     hair inbox: you labelled a photo from a player page, the photo was dropped and only its
                                  CLIP features (head crop and hair-region crop) and your labels were kept
Per target the training compares three feature sets by cross-validation (head crop, hair-region crop, both) and keeps the
best one. Without enough samples the rules in hair.py stay in charge."""
import json
import pickle
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "hair_model.pkl"
HAIR_DIR = ROOT / "training_hair"
LABELS = HAIR_DIR / "labels.json"
EMBEDDED = HAIR_DIR / "embedded.json"
TARGETS = ("HairStyle", "HairLength", "HairCurl", "HairFront", "HairParting", "HairHairline", "HairForehead", "HairBack")
RULE_TARGETS = ("HairStyle", "HairLength", "HairCurl")   # the ones hair.py has rules for
MIN_PHOTOS = 40   # below this the rules decide; a model on fewer samples only memorises them
VARIANTS = ("head", "hair", "both")


def _load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _feats(folder):
    """{file stem: (head embedding, hair-region embedding, rule guess)} for every photo in the folder (cached per file)."""
    from .encoder import encode
    from . import hair
    folder = Path(folder)
    if not folder.exists():
        return {}
    cache_f = ROOT / "data" / "hair_feats2.pkl"
    cache = pickle.load(open(cache_f, "rb")) if cache_f.exists() else {}
    out = {}
    for f in sorted(folder.iterdir()):
        if f.suffix == ".json":
            continue
        key = (str(f), f.stat().st_mtime)
        if key not in cache:
            try:
                _, box = encode(str(f), with_box=True)
                r = hair.analyze(str(f), box, use_model=False)
                cache[key] = (r["_emb"], r["_emb2"], r["_rules"])
            except ValueError as e:
                print(f"{f.name}: {e}"); continue
        out[f.stem] = cache[key]
    pickle.dump(cache, open(cache_f, "wb"))
    return out


def features(path):
    """Features of a photo at labelling time: (head, hair, rules). The photo itself is not touched."""
    from .encoder import encode
    from . import hair
    _, box = encode(str(path), with_box=True)
    r = hair.analyze(str(path), box, use_model=False)
    return r["_emb"], r["_emb2"], r["_rules"]


def add_embedded(label, head, hair_emb, rules, source):
    """Keep only features + labels of a photo that is dropped afterwards."""
    HAIR_DIR.mkdir(exist_ok=True)
    data = _load(EMBEDDED, [])
    data.append({"id": uuid.uuid4().hex[:8], "source": source, "label": label, "rules": rules,
                 "head": [round(float(x), 5) for x in np.ravel(head)], "hair": [round(float(x), 5) for x in np.ravel(hair_emb)]})
    EMBEDDED.write_text(json.dumps(data))
    return len(data)


def import_samples(path):
    """Merge a hair_samples.json (or the zip from the tool's export) from someone else; samples are matched by id. -> (new, total)"""
    import zipfile
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            new = json.loads(z.read("hair_samples.json"))
    else:
        new = json.loads(path.read_text())
    HAIR_DIR.mkdir(exist_ok=True)
    data = _load(EMBEDDED, [])
    have = {e["id"] for e in data}
    add = [e for e in new if e["id"] not in have and len(e.get("head", [])) == 512 and len(e.get("hair", [])) == 512
           and e.get("label", {}).get("HairStyle") is not None]
    EMBEDDED.write_text(json.dumps(data + add))
    return len(add), len(data) + len(add)


def samples(folder):
    """-> Xhead, Xhair, rules (list), {target: labels, -1 = not labelled}, (from dump, by hand, features only)"""
    from .hairdata import decode
    try:
        T = decode()
    except FileNotFoundError:
        T = {}
    rows = []
    for stem, (h, c, r) in _feats(folder).items():
        if stem.isdigit() and int(stem) in T:
            rows.append((h, c, r, T[int(stem)], 0))
    by_hand = _load(LABELS, {})
    for stem, (h, c, r) in _feats(HAIR_DIR).items():
        if stem in by_hand:
            rows.append((h, c, r, by_hand[stem], 1))
    for e in _load(EMBEDDED, []):
        rows.append((np.array(e["head"]), np.array(e["hair"]), e["rules"], e["label"], 2))
    if not rows:
        return np.zeros((0, 512)), np.zeros((0, 512)), [], {t: np.zeros(0, int) for t in TARGETS}, (0, 0, 0)
    Y = {t: np.array([max(0, int(r[3][t])) if r[3].get(t) is not None else -1 for r in rows]) for t in TARGETS}
    return (np.array([np.ravel(r[0]) for r in rows]), np.array([np.ravel(r[1]) for r in rows]), [r[2] for r in rows], Y,
            tuple(sum(r[4] == k for r in rows) for k in range(3)))


def counts():
    """How many hand-labelled samples per style (photos and features-only), for the UI."""
    c, total = {}, 0
    for lab in list(_load(LABELS, {}).values()) + [e["label"] for e in _load(EMBEDDED, [])]:
        total += 1
        c[lab["HairStyle"]] = c.get(lab["HairStyle"], 0) + 1
    return {"total": total, "by_style": c}


def _cv(clf, X, y):
    from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
    n_min = min(np.bincount(y)[np.bincount(y) > 0])
    cv = StratifiedKFold(min(5, n_min), shuffle=True, random_state=0) if n_min >= 2 else KFold(5, shuffle=True, random_state=0)
    return cross_val_predict(clf, X, y, cv=cv)


def train(folder):
    from sklearn.linear_model import LogisticRegression
    Xh, Xc, R, Y, (n_dump, n_hand, n_feat) = samples(folder)
    n = len(Xh)
    print(f"{n} Haar-Beispiele ({n_dump} mit Spieldaten, {n_hand} von dir beschriftete Fotos, {n_feat} aus dem Haar-Eingang)")
    X = {"head": Xh, "hair": Xc, "both": np.hstack([Xh, Xc]) if n else Xh}
    models = {}
    for t in TARGETS:
        m = Y[t] >= 0
        y = Y[t][m]
        if len(y) == 0 or len(set(y)) < 2:
            models[t] = None
            continue
        base = np.bincount(y).max() / len(y)
        line, best = f"  {t}: {len(y)} Beispiele, Mehrheit {base:.2f}", ("head", -1.0)
        if len(y) >= 10:
            if t in RULE_TARGETS:
                rr = [(r.get(t), yy) for r, yy, ok in zip(R, Y[t], m) if ok and r.get(t) is not None]
                line += f" | Regeln {np.mean([a == b for a, b in rr]):.2f}" if rr else ""
            for v in VARIANTS:
                acc = float(np.mean(_cv(LogisticRegression(C=2.0, max_iter=3000), X[v][m], y) == y))
                line += f" | {v} {acc:.2f}"
                if acc > best[1] + 1e-9:
                    best = (v, acc)
            line += f" -> nimmt: {best[0]}"
        print(line)
        models[t] = (best[0], LogisticRegression(C=2.0, max_iter=3000).fit(X[best[0]][m], y))
    pickle.dump({"models": models, "n": n}, open(MODEL, "wb"))
    print("gespeichert:", MODEL, "| " + (f"wird ab {MIN_PHOTOS} Beispielen benutzt" if n < MIN_PHOTOS else "ist aktiv"))



def predict(emb, emb2, rules):
    """Model output for the targets, or {} while there are too few samples."""
    if not MODEL.exists():
        return {}
    b = pickle.load(open(MODEL, "rb"))
    if b["n"] < MIN_PHOTOS:
        return {}
    out = {}
    for t, mv in b["models"].items():
        if mv is None:
            continue
        v, clf = mv
        x = emb if v == "head" else emb2 if v == "hair" else np.concatenate([emb, emb2])
        out[t] = int(clf.predict(x[None])[0])
    return out
