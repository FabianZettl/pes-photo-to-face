"""Sanity checks for the FM -> PES conversion. Run: python tests/check_stats.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pesface import stats

striker = {"Finishing": "19", "Off the Ball": "18", "Composure": "17", "Pace": "12", "Heading": "14", "Strength": "15"}
r = stats.convert(striker)
assert 90 <= r["Finishing"] <= 99 and r["Speed"] == 74 and "GKReflexes" not in r, r      # outfielder: no GK stats
assert all(40 <= v <= 99 for v in r.values())
gk = {"Handling": "17", "Reflexes": "18", "Aerial Reach": "16", "Kicking": "13"}
g = stats.convert(gk)
assert g["GKReflexes"] >= 90 and g["GKCatching"] == 89, g
assert stats.convert({"Finishing": "n/a"}) == {}
assert stats.convert({"Free Kick Taking": "10"}).get("PlaceKicking") == 68        # alias works
print("stats ok")
