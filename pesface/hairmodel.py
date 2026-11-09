"""Learned hair model: CLIP embedding of the head crop -> style / length / curl. Two kinds of training photos:
  training/<player id>.<ext>      labels = the player's in-game values (appearance dump)
  training_hair/<n>.<ext>         labels = what the user chose in the Haare tab (labels.json), no player needed
Without enough photos the rules in hair.py stay in charge."""
import json
import pickle
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "hair_model.pkl"
HAIR_DIR = ROOT / "training_hair"
LABELS = HAIR_DIR / "labels.json"
TARGETS = ("HairStyle", "HairLength", "HairCurl", "HairFront", "HairParting", "HairHairline", "HairForehead", "HairBack")
MIN_PHOTOS = 40   # below this the rules decide; a model on fewer photos only memorises them


def _embs(folder):
    """{file stem: CLIP embedding of the head crop} for every photo in the folder (cached in data/hair_feats.pkl)."""
    from .encoder import encode
    from . import hair
    import cv2
    folder = Path(folder)
    if not folder.exists():
        return {}
    cache_f = ROOT / "data" / "hair_feats.pkl"
    cache = pickle.load(open(cache_f, "rb")) if cache_f.exists() else {}
    out = {}
    for f in sorted(folder.iterdir()):
        if f.suffix == ".json":
            continue
        key = (str(f), f.stat().st_mtime)
        if key not in cache:
            try:
                _, box = encode(str(f), with_box=True)
                _, cache[key] = hair.clip_style(cv2.cvtColor(cv2.imread(str(f)), cv2.COLOR_BGR2RGB), box)
            except ValueError as e:
                print(f"{f.name}: {e}"); continue
        out[f.stem] = cache[key]
    pickle.dump(cache, open(cache_f, "wb"))
    return out


def samples(folder):
    """-> X, {target: labels}, n_from_dump, n_by_hand"""
    from .hairdata import decode
    try:
        T = decode()
    except FileNotFoundError:
        T = {}
    X, Y, rows = [], {t: [] for t in TARGETS}, []
    for stem, emb in _embs(folder).items():
        if stem.isdigit() and int(stem) in T:
            rows.append((emb, T[int(stem)], 0))
    by_hand = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    for stem, emb in _embs(HAIR_DIR).items():
        if stem in by_hand:
            rows.append((emb, by_hand[stem], 1))
    for emb, lab, _ in rows:
        X.append(emb)
        for t in TARGETS:
            Y[t].append(max(0, int(lab[t])) if lab.get(t) is not None else -1)   # -1 = not labelled
    return np.array(X), {t: np.array(v) for t, v in Y.items()}, sum(r[2] == 0 for r in rows), sum(r[2] == 1 for r in rows)


def counts():
    """How many hand-labelled photos per style, for the UI."""
    by_hand = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    c = {}
    for lab in by_hand.values():
        c[lab["HairStyle"]] = c.get(lab["HairStyle"], 0) + 1
    return {"total": len(by_hand), "by_style": c}


def train(folder):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict, StratifiedKFold, KFold
    X, Y, n_dump, n_hand = samples(folder)
    n = len(X)
    print(f"{n} Haar-Fotos ({n_dump} mit Spieldaten, {n_hand} von dir beschriftet)")
    models = {}
    for t in TARGETS:
        m = Y[t] >= 0
        y, Xt = Y[t][m], X[m]
        if len(y) == 0 or len(set(y)) < 2:
            models[t] = None
            continue
        base = np.bincount(y).max() / len(y)
        n_min = min(np.bincount(y)[np.bincount(y) > 0])
        clf = LogisticRegression(C=2.0, max_iter=2000)
        if len(y) >= 10:
            cv = StratifiedKFold(min(5, n_min), shuffle=True, random_state=0) if n_min >= 2 else KFold(5, shuffle=True, random_state=0)
            pred = cross_val_predict(clf, Xt, y, cv=cv)
            print(f"  {t}: {len(y)} Fotos, Kreuzvalidierung {np.mean(pred == y):.2f} (immer die häufigste Klasse: {base:.2f})"
                  + (f"; Kräuselung ±1: {np.mean(abs(pred - y) <= 1):.2f}" if t == "HairCurl" else ""))
        models[t] = clf.fit(Xt, y)
    pickle.dump({"models": models, "n": n}, open(MODEL, "wb"))
    print("gespeichert:", MODEL, "| " + (f"wird ab {MIN_PHOTOS} Fotos benutzt" if n < MIN_PHOTOS else "ist aktiv"))


def predict(emb, rules):
    """Model output for the targets, or {} while there are too few training photos."""
    if not MODEL.exists():
        return {}
    b = pickle.load(open(MODEL, "rb"))
    if b["n"] < MIN_PHOTOS:
        return {}
    return {t: int(m.predict(emb[None])[0]) for t, m in b["models"].items() if m is not None}
