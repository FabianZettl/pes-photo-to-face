"""FM attributes (1-20, as FMInside shows them) -> the 25 PES attributes (40-99) that sit in the game's player block.
A rough, transparent mapping: every PES stat is a weighted mean of the FM attributes that mean about the same thing.
Fields and offsets are the ones GrowthBridge (Karijera 26) writes; see sider/faceai_stats.lua."""
import csv
import re
from pathlib import Path

# PES stat -> {FM attribute (normalised): weight}
MAP = {
    "OffensiveAwareness": {"offtheball": 3, "anticipation": 1, "decisions": 1, "composure": 1},
    "BallControl": {"firsttouch": 2, "technique": 2, "dribbling": 1},
    "Dribbling": {"dribbling": 3, "agility": 1, "flair": 1},
    "TightPossession": {"technique": 2, "composure": 2, "balance": 1, "strength": 1},
    "Finishing": {"finishing": 4, "composure": 1},
    "LowPass": {"passing": 3, "vision": 1, "technique": 1},
    "LoftedPass": {"passing": 2, "technique": 2, "vision": 1, "crossing": 1},
    "Heading": {"heading": 3, "jumpingreach": 1, "bravery": 1},
    "PlaceKicking": {"freekicktaking": 2, "penaltytaking": 2, "corners": 1},
    "Curl": {"technique": 2, "freekicktaking": 1, "crossing": 1, "corners": 1},
    "Speed": {"pace": 1},
    "Acceleration": {"acceleration": 1},
    "KickingPower": {"longshots": 2, "strength": 1, "technique": 1},
    "Jump": {"jumpingreach": 1},
    "PhysicalContact": {"strength": 3, "bravery": 1, "balance": 1},
    "Balance": {"balance": 2, "agility": 2},
    "Stamina": {"stamina": 3, "naturalfitness": 2, "workrate": 1},
    "DefensiveAwareness": {"positioning": 2, "marking": 2, "anticipation": 1, "concentration": 1},
    "BallWinning": {"tackling": 3, "aggression": 1, "bravery": 1},
    "Aggression": {"aggression": 3, "bravery": 1, "determination": 1},
}
GK = {   # only written for goalkeepers
    "GKAwareness": {"positioning": 1, "anticipation": 1, "commandofarea": 2, "concentration": 1},
    "GKCatching": {"handling": 1},
    "GKClearing": {"kicking": 2, "throwing": 1},
    "GKReflexes": {"reflexes": 3, "agility": 1},
    "GKReach": {"aerialreach": 2, "oneonones": 1},
}
COLUMNS = list(MAP) + list(GK)
ALIAS = {"freekicks": "freekicktaking", "penalties": "penaltytaking", "jumping": "jumpingreach", "aerialability": "aerialreach",
         "commandofarea": "commandofarea", "firsttouch": "firsttouch"}


def _norm(k):
    k = re.sub(r"[^a-z0-9]", "", k.lower())
    return ALIAS.get(k, k)


def _scale(fm):
    """FM 1..20 -> PES 41..98 (FM 10 = 68, 15 = 83, 18 = 92)."""
    return int(max(40, min(99, round(38 + 3 * fm))))


def convert(fm_stats):
    """{FM attribute name: value or text} -> {PES stat: 40..99}. Stats whose source attributes are all missing are left out."""
    a = {}
    for k, v in fm_stats.items():
        m = re.search(r"\d+", str(v))
        if m and 1 <= int(m.group()) <= 20:
            a[_norm(k)] = int(m.group())
    is_gk = (a.get("handling", 1) + a.get("reflexes", 1)) / 2 >= 10
    out = {}
    for pes, w in {**MAP, **(GK if is_gk else {})}.items():
        have = {k: x for k, x in w.items() if k in a}
        if have:
            out[pes] = _scale(sum(a[k] * x for k, x in have.items()) / sum(have.values()))
    return out


def queue(path, player_id, stats):
    """Add or replace the row of a player in faceai_stats.csv (kept for good: the table is rebuilt at every start)."""
    path = Path(path)
    rows = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            rows = {r["Id"]: r for r in csv.DictReader(f) if r.get("Id")}
    rows[str(player_id)] = {"Id": str(player_id), **{k: str(v) for k, v in stats.items()}}
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["Id", *COLUMNS], restval="", extrasaction="ignore", lineterminator="\r\n")
        w.writeheader(); w.writerows(rows.values())
    tmp.replace(path)
