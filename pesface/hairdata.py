"""Ground truth for hair from an appearance dump (faceai_probe F8) + comparison with the photo guess."""
import glob
import json
import os
from pathlib import Path

import numpy as np

# Folder shared with the Sider module: <SiderAddons>/content/faceai (set FACEAI_DIR); default ./faceai next to the project.
FACEAI_DIR = Path(os.environ.get("FACEAI_DIR", Path(__file__).resolve().parent.parent / "faceai"))
DUMPS = str(FACEAI_DIR / "dump_*.bin")
STYLE = {0: "?0", 1: "Normal", 2: "Trocken", 3: "Iro", 4: "Afro", 5: "Dreadlocks", 6: "Geflochten", 7: "Spezial"}
LENGTH = {0: "?0", 1: "rasiert", 2: "Sehr kurz", 3: "Kurz", 4: "Mittel", 5: "Lang"}


def truth(dump=None):
    """{player_id: {HairStyle, HairLength, HairCurl, HairColourR/G/B, HairColourType}} for every record in the dump."""
    dump = dump or sorted(glob.glob(DUMPS))[-1]
    a = np.fromfile(dump, np.uint8).reshape(-1, 72)
    ids = a[:, :4].copy().view("<u4").ravel()
    b = np.unpackbits(a, axis=1, bitorder="little").astype(int)
    f = lambda pos, w: sum(b[:, pos + k] << k for k in range(w))
    cols = {"HairStyle": f(448, 3), "HairLength": f(480, 3), "HairCurl": f(483, 3) - 1, "HairColourType": f(524, 3),
            "HairColourR": f(430, 6), "HairColourG": f(436, 6), "HairColourB": f(442, 6)}
    return {int(i): {k: int(v[n]) for k, v in cols.items()} for n, i in enumerate(ids)}


def evaluate(folder):
    from .encoder import predict_all
    T = truth()
    rows = []
    for f in sorted(Path(folder).iterdir()):
        if not f.stem.isdigit() or int(f.stem) not in T:
            continue
        t = T[int(f.stem)]
        try:
            p = predict_all(str(f))
        except ValueError as e:
            print(f"{f.name}: {e}"); continue
        rows.append((f.stem, t, p))
        print(f"{f.stem:>7}  Stil {STYLE[t['HairStyle']]:>10} -> {STYLE[p['HairStyle']]:<10} | Länge {LENGTH.get(t['HairLength'], t['HairLength']):>9} -> "
              f"{LENGTH.get(p['HairLength'], p['HairLength']):<9} | Kräusel {t['HairCurl']:>2} -> {p['HairCurl']} | Farbe "
              f"{t['HairColourR']},{t['HairColourG']},{t['HairColourB']} (Typ {t['HairColourType']}) -> {p['HairColourR']},{p['HairColourG']},{p['HairColourB']}")
    n = max(1, len(rows))
    print(f"\n{len(rows)} Fotos | Stil richtig {sum(t['HairStyle']==p['HairStyle'] for _,t,p in rows)}/{n} | "
          f"Länge richtig {sum(t['HairLength']==p['HairLength'] for _,t,p in rows)}/{n} | "
          f"Kräuselung ±1 {sum(abs(t['HairCurl']-p['HairCurl'])<=1 for _,t,p in rows)}/{n}")


def latest_dump():
    fs = sorted(glob.glob(DUMPS), key=lambda f: Path(f).stat().st_mtime)
    return fs[-1] if fs else None


def decode(dump=None):
    """{player_id: {slider/hair column: value}} for every field in data/layout.json (value = field - bias)."""
    dump = dump or latest_dump()
    if not dump:
        raise FileNotFoundError("kein Dump gefunden: im Spiel faceai_probe F8 drücken")
    lay = json.loads((Path(__file__).resolve().parent.parent / "data" / "layout.json").read_text())
    a = np.fromfile(dump, np.uint8).reshape(-1, 72)
    ids = a[:, :4].copy().view("<u4").ravel()
    b = np.unpackbits(a, axis=1, bitorder="little").astype(int)
    cols = {n: sum(b[:, v["pos"] + k] << k for k in range(v["w"])) - v["bias"] for n, v in lay.items()}
    return {int(i): {n: int(c[k]) for n, c in cols.items()} for k, i in enumerate(ids)}
