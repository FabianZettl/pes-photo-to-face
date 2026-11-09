# PES Photo → Face

Builds **faces for the new players of an [FL Mod Studio](https://github.com/Matozanato/FootballLife-new-leagues) world** (Football
Life 2026/2027, PES 2021 engine) from **photos**, and applies them **live in the running game**. It turns a photo into the
Edit-mode appearance of a player (skin tone, eyes, brows, nose, mouth, chin, ears, beard, hair style, length, curl, colour …),
stores it, and a small Sider module writes it into the game's appearance table within seconds. No restart per face.

> **Status.** Working in the author's Football Life 2027 setup: a face built in the tool showed up in the running game right
> away. The estimates are good starting points, not perfect likenesses (see [Limits](#limits-please-read)). The record layout
> and the way the module gets past `fl26regen`'s pack faces are documented so that other tools can reuse them.

## What it does with FL Mod Studio

FL Mod Studio builds worlds with new leagues, clubs and players. Those new players have no face of their own: `fl26regen` gives
each of them a **pack face** by nationality. This tool replaces the pack face of the players you choose with a face made from a photo.

```
FL Mod Studio build ──► fl26playerids.json   who the new players are (game id, name, club, birth date, NewLife id)
(read only)             fl26world.txt        which of them have the generic pack face
                        NewLife release zips ratings, club names

photo ──► this tool ──► face values per player, stored under the NewLife id
                         │  "Mit Build abgleichen" (automatic after a build)
                         ▼
                  faceai_newworld.csv + fingerprint of the build ──► faceai.lua (Sider module) ──► game appearance table
```

- **Reads, never changes, Mod Studio's files.** `fl26playerids.json`, `fl26world.txt` and the NewLife zips are only read.
- **Stable across builds.** Mod Studio hands out the game id of a new player at Build ("first free id"), and it can change. Faces
  are stored under the NewLife id; every Sync writes the *current* game ids plus a fingerprint of that build's
  `fl26playerids.json`. The module uses the rows only while the fingerprint matches, so a face can never land on the wrong
  player after a rebuild (it logs that a new Sync is needed instead).
- **Live, next to `fl26regen`.** `fl26regen.dll` copies its pack face over the appearance record of every player in its
  new-player list every 250 ms, also over a record we wrote. `faceai.lua` finds that list in the DLL's data, sets the pack-face
  index of the players it manages to -1 (the DLL then leaves them alone) and redirects their portrait itself. It does this right
  before it writes a record and again whenever the DLL rebuilds its list. Details: [docs/how-it-works.md](docs/how-it-works.md).
- **Rendered faces are respected.** Players that already have a rendered face model in a face pack
  (`livecpk/*/Asset/model/character/face/real/<id>/`) are detected and need nothing.
- **Needs room in the appearance table**, which FL Mod Studio's `fl26appcap` module provides (65,000 records).

## Daily use

Open the tool (`python -m pesface serve`, http://localhost:8000). It opens on **New World**:

1. **Pick a team** (or search). The list shows every new player of the last build with club, birth date and strength, and who
   still needs a face.
2. **Get a photo** (see [Photo sources](#photo-sources)).
3. **Build:** **Berechnen** builds one player from his photo, **Alle mit Foto berechnen** every player that has one, **Team bauen** fetches the free Commons portraits of one team,
   builds the faces and syncs. A face built from the browser hand-off is synced at once.
4. **In game:** within a few seconds the module writes the record; the 3D model shows the new face when the game loads the player
   again (match, Edit). The 2D portrait in lists stays the pack portrait.
5. **Not happy with a face?** **Neu berechnen** rebuilds it from the stored photo; **Zurücksetzen** removes face, photo and credit
   so the player needs a build again (a running game keeps the face until the next start).

Normal mode shows only New World (plus *Eingang* while a page you sent from the browser waits for your confirmation). The other
tools (*Erkennen*, *Bulk*, *Training*, *Haare*) sit behind the **Dev** switch at the top right.

## Photo sources

The tool never crawls a site. Photos come only like this:

- **Wikimedia Commons, on request.** **Commons-Foto** on a row looks the player up on Wikidata (same birth date, similar name),
  shows the portrait with author and licence, and downloads it only when you press *Übernehmen*. **Team prüfen** / **Sichtbare auf
  Commons prüfen** ask metadata only. Only CC0, public domain, CC BY and CC BY-SA files of at least 400 px are offered; author,
  licence and source are kept with the photo (`newworld_photos/credits.json`). On a sample of 600 players about 17 % of the new
  players had a free Commons photo (roughly 40 % of the strongest 1,000, 10 % of the weakest). Requests are throttled to one per
  second.
- **Browser hand-off for pages you open yourself** (FMInside, Transfermarkt, SoFIFA; `userscript/`). One click on a player page
  sends name, club, birth date and photo to your local tool. The tool matches the player; an exact match (equal birth date,
  nearly equal name) is built immediately, anything less certain waits in *Eingang* for your confirmation. **The photo is used
  once and dropped: it is never stored, shared or used for training.** Every click ends in a visible result (button state,
  toast). The selectors are best guesses (the sites block automated access); see the limits.
- **Photos you drop in** (on a row, or a folder of `<playerID>.jpg` via the Dev *Bulk* tab).
- Photos should be front-facing, hair visible, ideally ≥ 800 px; the tool warns about small ones.

Respect each site's terms. FMInside reserves its content against AI training and kicker blocks AI crawlers, so neither is a
source for training data. SoFIFA's player images are EA's game renders, Transfermarkt's are agency photos.

## Install

Needs Python 3.11 (DeepFace/TensorFlow) and a Football Life / PES 2021 Sider setup with FL Mod Studio's modules.

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # torch: use the CPU build, see requirements.txt
python -m pesface fetch-base-data          # base training data of the original project, see Credits
python -m pesface train                    # trains the face model (seconds)

export FACEAI_DIR="/path/to/SiderAddons/content/faceai"   # shared with the Sider module
export NEWLIFE_DIR="/path/to/NewLife-release-zips"        # optional: ratings and club names
python -m pesface serve                    # http://localhost:8000
```

**Game side**
1. Copy `sider/faceai.lua` (and, if you want to analyse dumps, `sider/faceai_probe.lua`) to `SiderAddons/modules/`.
2. Create the folder `SiderAddons/content/faceai/`.
3. Add `lua.module = "faceai.lua"` to `sider.ini` (it needs `luajit.ext.enabled = 1` for safe memory reads; without it only F9 works). It runs by itself every
   few seconds after that; **F9** in the Sider overlay (module `faceai` selected) applies at once.
4. Optional player search by name/team: build the list from your own game data with
   `python -m pesface players players_dump.bin dump_XXXX.bin <folder with Team.bin and PlayerAssignment.bin>`.

## Quality and training

Face sliders: a ridge regression on FaceNet embeddings (about 1,000 players from the original project as base data; cross-validated
about 20 % better than predicting the average; skin tone, nose and brows work, head/ear proportions hardly). Hair: rules on a MediaPipe
hair mask plus a zero-shot CLIP step for braids, locks, afro and mohawk; colour is snapped to the game's seven presets; beard is a
CLIP decision (none / stubble / full). With about 40 labelled photos a classifier takes over the hair options. In the Dev tabs you add
training photos with their in-game values (*Training*) or label hair yourself (*Haare*) and retrain.

## Use the layout in your own tool

[docs/appearance-record.md](docs/appearance-record.md) lists every field of the 72-byte appearance record with its evidence, and
[docs/how-it-works.md](docs/how-it-works.md) explains how it was found (dump the table, change one option in Edit, diff). Reading one
slider is:

```python
def get(record: bytes, pos: int, width: int, bias: int) -> int:
    bits = int.from_bytes(record, "little")      # 72 bytes, bit n = byte n//8, bit n%8
    return ((bits >> pos) & ((1 << width) - 1)) - bias
```

Tests: `tests/check_layout.py` (no overlapping fields), `check_stats.py` (stat conversion), `check_fingerprint.py` (build fingerprint,
Python vs Lua), `check_commons.py` (licence filter), `check_userscript.py` and `check_userscript_feedback.py` (page scraper and the
click feedback, against fixtures), `check_release.py` (the live take-over from `fl26regen`, against a fake process).

## Limits (please read)

- Confirmed live in a real game for a built player; broad testing across many players and screens is still to be done. Whether a
  face appears also depends on the screen: the 3D model uses the record, the 2D portrait in lists stays the pack portrait.
- The take-over from `fl26regen` is built from that DLL's source (list layout: u32 id, i16 face, u8 keep, u8 pad). A different
  `fl26regen` version could differ; `sider.log` then says `could not find fl26regen's list` and the pack face may overwrite ours.
- Verified only on the Football Life 2027 build (`FL_2027.exe`). The in-memory table is verified; the on-disk `PlayerAppearance.bin`
  container is *not* verified to use the same record layout.
- A few fields are loose guesses (head length/width/depth, upper eyelid type, laughter lines) and some menu values are inferred from menu
  order; [the record doc](docs/appearance-record.md) marks every field with its evidence.
- Hair and beard are heuristics. Small photos (SoFIFA thumbnails are 120 px) give weak results.
- The user script's selectors for Transfermarkt and SoFIFA could only be tested against fixtures and, for SoFIFA, a few real pages.
- `faceai_stats.lua` (Football Manager attributes → PES stats, via the FMInside hand-off) is experimental and not verified in game.

## Credits

- **[FL Mod Studio](https://github.com/Matozanato/FootballLife-new-leagues) (Matozanato, MIT)** – the worlds and NewLife releases
  this tool works on. Its documentation and the source of `fl26regen`, `fl26appcap` and the world file were the reference for how new
  players get their faces; this tool only reads its output.
- **AlirezaF80** – [PES-Edit-Face-AI](https://github.com/AlirezaF80/PES-Edit-Face-AI): the original idea (face embedding → slider values)
  and the base training data, which this tool downloads from there (`fetch-base-data`) and does **not** redistribute, because that
  repository has no licence. This is a from-scratch rewrite of the idea.
- **juce** – Sider (PES Sider, announced on the evo-web forum), which makes in-game Lua modules possible.
- **Karijera 26** – `PlayerDump` (optional source of the player list) and `GrowthBridge`, whose documented player-block layout
  (7-bit attribute fields) `faceai_stats.lua` uses. Not included.
- **Wikimedia Commons / Wikidata** – portraits offered on request, with the photographers' attribution kept.
- **DeepFace** (Sefik Ilkin Serengil) and **FaceNet** – face embeddings. **MediaPipe** (Google, Apache-2.0) – hair segmentation, downloaded
  on first use. **OpenAI CLIP** via Hugging Face Transformers – zero-shot hair and beard step. scikit-learn, PyTorch, OpenCV, FastAPI.

## Legal

Unofficial fan tool, not affiliated with Konami or any mod team. No game files, player data, photos or trained models are included.
You need your own copy of the game. Make sure you may use the photos you feed in.

## License

MIT, see [LICENSE](LICENSE).
