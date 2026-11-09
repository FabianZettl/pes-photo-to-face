# PES Photo → Face

Turn a **photo** into the **Edit-mode face settings** of a PES player (eFootball PES 2021 SEASON UPDATE engine, used by
Football Life / patch setups): skin tone, eyes, brows, nose, mouth, chin, ears, beard, and the hair menu
(style, length, curl, parting, colour …). The values go into a CSV; a small Sider module
applies them to the players in game. Works for single players or a whole folder of photos named after player IDs.

It is an estimate, not magic. The result is a good starting point that you fine-tune in the editor.

> **Status: experimental.** Everything described here was checked in a Football Life 2027 setup. Offsets and
> field layouts are for that build; see [docs/how-it-works.md](docs/how-it-works.md) for what is verified and what is not.

## What is in the box

| Part | What it does |
|---|---|
| `pesface/` + `web/` | Python tool with a web UI: photo → values → CSV queue. Tabs: *Erkennen* (recognise), *Training*, *Haare* (hand-label hair), *Bulk* (folder of photos). |
| `sider/faceai.lua` | Sider module: reads the CSV, writes the values into the game's appearance table, inserts records for players that have none (new-world players). |
| `sider/faceai_probe.lua` | Read-only helper: dumps the appearance table (F8) – this is how the record layout was reverse-engineered, and how you check your own build. |
| `userscript/` + `pesface/stats.py` + `sider/faceai_stats.lua` | Optional FMInside hand-off: one click on a player page *you opened* sends name, club, stats and photo to the local tool; stats are converted to PES values and written by `faceai_stats.lua`. |
| `data/layout.json`, [docs/appearance-record.md](docs/appearance-record.md) | The 72-byte appearance record: which bits hold which setting. **This is the part other tools can reuse.** |

## Quick start

Needs Python 3.11 (DeepFace/TensorFlow) and a Football Life / PES 2021 Sider setup.

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # torch: use the CPU build, see requirements.txt
python -m pesface fetch-base-data          # base training data of the original project, see Credits
python -m pesface train                    # trains the face model (seconds)

export FACEAI_DIR="/path/to/SiderAddons/content/faceai"   # shared with the Sider module
python -m pesface serve                    # http://localhost:8000
```

**Game side**
1. Copy `sider/faceai.lua` (and, if you want to analyse dumps, `sider/faceai_probe.lua`) to `SiderAddons/modules/`.
2. Create the folder `SiderAddons/content/faceai/`.
3. Add `lua.module = "faceai.lua"` to `sider.ini`. If you use the `fl26regen` module, list `faceai.lua` **before** it
   (see [docs/how-it-works.md](docs/how-it-works.md#new-world-players)).
4. In game open the Sider overlay (the key set by `overlay.vkey.toggle` in `sider.ini`), select the `faceai` module, **F9** applies the queue.

**Using it**
- *Erkennen*: drop a photo, optionally pick hair options, **In Queue**.
- *Bulk*: type the folder path (files named `<playerID>.jpg`), **Alle verarbeiten**. Same from the command line:
  `python -m pesface queue /path/to/folder`.
- In game press **F9**: every player in the queue is written, then removed from `faceai.csv` and copied to
  `faceai_done.csv`.
- Photos: front-facing, hair visible, at least ~800 px. Tiny photos give poor results (the UI warns you).

**Optional: player search by name/team.** Build the list from your own game data:
`PlayerDump` (F7 of the Karijera 26 module) writes `players_dump.bin`; then
`python -m pesface players players_dump.bin dump_XXXX.bin <folder with Team.bin and PlayerAssignment.bin>`.
Without it you can still type player IDs.

## FMInside hand-off (optional)

For players that exist in your database, take the photo and the Football Manager values from their FMInside page:

1. Install `userscript/fminside-to-pes-face-ai.user.js` in Tampermonkey/Violentmonkey.
2. Open a player page on fminside.net yourself and click **→ PES Face AI**. Nothing is crawled or searched: the script reads
   the one page you are on and hands it to your local server (`localhost:8000`).
3. In the tool open the **FM** tab. The player is matched against your player list by name and club; you confirm (or pick
   another player) and press *Übernehmen*. The face goes into `faceai.csv`, the converted stats into `faceai_stats.csv`.
   The photo stays in memory only and is dropped when you confirm; it is never used for training.
4. In game: **F9** (`faceai.lua`) writes the face. For the stats press **F7** in PlayerDump once per launch (it writes the
   table address), then **F5** in `faceai_stats.lua`.

The FM → PES conversion (`pesface/stats.py`) is a simple weighted mapping, not a calibrated converter. The userscript's
selectors are best guesses for the current FMInside layout; if the site changes it tells you what it could not find.
Respect the site's terms: it reserves its content against AI training, so photos from it must not go into the training
folders. `faceai_stats.lua` is experimental: not yet verified in game; every write is read back and logged.

## Training

- **Face:** the base model uses ~1,000 players from the original project. In the *Training* tab you add photos of
  players together with their current in-game values (read from a dump) and retrain.
- **Hair:** the *Haare* tab lets you label a photo yourself ("this is how I would build it in game"). Rules plus a
  zero-shot CLIP step guess the hair; once about 40 labelled photos exist a small classifier takes over.

## Use the layout in your own tool

[docs/appearance-record.md](docs/appearance-record.md) lists every field. Reading one slider is:

```python
def get(record: bytes, pos: int, width: int, bias: int) -> int:
    bits = int.from_bytes(record, "little")      # 72 bytes, bit n = byte n//8, bit n%8
    return ((bits >> pos) & ((1 << width) - 1)) - bias
```

Writing is the reverse. `tests/check_layout.py` checks the table for overlaps, `tests/check_stats.py` the stat conversion.

## Limits (please read)

- Verified only on the Football Life 2027 build (`FL_2027.exe`). Other builds may use other offsets.
- The in-memory table is verified. The on-disk `PlayerAppearance.bin` container (zlib) is *not* verified to use the same
  record layout.
- A few fields are loose guesses (head length/width/depth, upper eyelid type, laughter lines) and some menu values are
  inferred from menu order. [The record doc](docs/appearance-record.md) marks every field with its evidence.
- Written values live in memory. I have not verified that they survive saving the Edit data and restarting; for
  players without a record the module re-inserts them from `faceai_done.csv` at every start.
- Beard types and hair colour are heuristics. Colour is snapped to the game's seven presets.

## Credits

- **AlirezaF80** – [PES-Edit-Face-AI](https://github.com/AlirezaF80/PES-Edit-Face-AI): the original idea (face embedding →
  slider values) and the base training data, which this tool downloads from there (`fetch-base-data`) and does **not**
  redistribute, because that repository has no licence. This is a from-scratch rewrite of the idea.
- **juce** – Sider (PES Sider, announced on the evo-web forum), which makes in-game Lua modules possible.
- The **Football Life 26/27 module set** (`fl26appcap`, `fl26regen`, FL26 Mod Studio) – their comments documented the
  appearance table size and how new-world players get faces; `faceai.lua` is written to coexist with them.
- **Karijera 26** – `PlayerDump` (optional source of the player list) and `GrowthBridge`, whose documented player-block layout (7-bit attribute fields) `faceai_stats.lua` uses. Not included.
- **DeepFace** (Sefik Ilkin Serengil) and **FaceNet** – face embeddings.
- **MediaPipe** (Google, Apache-2.0) – hair segmentation model, downloaded on first use.
- **OpenAI CLIP** via Hugging Face Transformers – zero-shot hairstyle step.
- scikit-learn, PyTorch, OpenCV, FastAPI.

## Legal

Unofficial fan tool, not affiliated with Konami or any mod team. No game files, player data, photos or trained models
are included. You need your own copy of the game. Make sure you may use the photos you feed in.

## License

MIT, see [LICENSE](LICENSE).
