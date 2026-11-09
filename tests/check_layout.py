"""Sanity check for data/layout.json: no two fields share a bit, every value range fits its bit width,
the id occupies bits 0-31. Run: python tests/check_layout.py"""
import json
from pathlib import Path

L = json.loads((Path(__file__).resolve().parent.parent / "data" / "layout.json").read_text())
used = {}
for name, f in L.items():
    assert f["pos"] >= 32 and f["pos"] + f["w"] <= 576, name
    for b in range(f["pos"], f["pos"] + f["w"]):
        assert b not in used, f"{name} overlaps {used[b]} at bit {b}"
        used[b] = name
    assert 0 <= f["lo"] + f["bias"] and f["hi"] + f["bias"] < 2 ** f["w"], f"{name}: range does not fit {f['w']} bits"
print(f"layout ok: {len(L)} fields, {len(used)} of 544 bits used")
