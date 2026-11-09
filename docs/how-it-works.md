# How it works

This page explains the whole process, including how the record layout was found, so you can verify it, repeat it for
another build, or reuse it in other tools.

## 1. The idea

For every player the game keeps an *appearance record*: skin, hair, body and all the face sliders of the Edit mode.
If we can predict those numbers from a photo and write them into that record, the face is built automatically.

```
photo ──► face embedding (Facenet) ──► ridge regression ──► face sliders
      └─► hair mask (MediaPipe) + CLIP + rules/classifier ──► hair menu, colour preset, beard
                                  │
                                  ▼
                         faceai.csv  (Id, one column per field)
                                  │
                       Sider module faceai.lua (F9)
                                  ▼
                 PlayerAppearance table in game memory
```

The slider model is a rewrite of the idea in [AlirezaF80/PES-Edit-Face-AI](https://github.com/AlirezaF80/PES-Edit-Face-AI):
face embedding in, one slider value out per column. Their data (about 1,000 players with face embeddings and ~25,000
players with slider values) is the base training set. Cross-validated, the model beats "always predict the average" by
about 20 % on average; skin tone, nose and brows work well, head/ear proportions hardly at all (an identity embedding
carries little geometry).

## 2. Where the data lives

The game holds all appearance records in one table in memory:

| What | Where (Football Life 2027, `FL_2027.exe`) |
|---|---|
| table object | `[exe + 0x3705E10] → +0x60` |
| first record | object + `0x50910` |
| record size | 72 bytes |
| record count | u16 at object + `0x260552` (stock, 30,024 records) or `+0x4C7252` with the `fl26appcap` module (65,000) |

These constants are from the comments in the `fl26appcap` / `fl26regen` modules and were confirmed by dumping the table
(`faceai_probe.lua`, F8): 26,395 records, sorted by player id, id = first u32.

**Other builds:** the offsets will differ. Find the table by dumping memory and looking for a sorted run of 72-byte
records starting with player IDs.

## 3. How the record layout was found

1. **Dump** the table with `faceai_probe.lua` (F8) → `dump_HHMMSS_NN.bin`.
2. **Statistics.** Join the dump with a CSV that has the slider values of ~9,000 of the same players. For every
   slider, test every bit position and width and keep the one where the stored number is a fixed function of the CSV
   value. Signed sliders (−7…+7) turned out to be stored as `value + 7` in 4 bits, typed options as `value − 1`.
   Matches are 94-98 % for most sliders (the rest is data that changed between versions). Weak ones are marked in
   [appearance-record.md](appearance-record.md).
3. **Edit-mode experiments** for everything the CSV does not know (hair): take a dump, change *one* option in the
   player editor, confirm, take a dump, diff. Exactly one record changes and only the bits of that option flip.
   Repeating this over a menu gives the value of every entry (Stil 2 = Trocken, 3 = Iro, 4 = Afro, …).
4. **Palette.** 99 % of players use one of seven hair colour presets; their RGB values appear in the same record, so a
   photo only has to be classified into one of seven presets.

## 4. Writing values: the Sider module

`faceai.lua` reads `content/faceai/faceai.csv` and, per row, patches the matching 72-byte record in memory (only the
fields named in the CSV). The game picks the change up immediately; no save or reload was needed in my tests.

CSV: header `Id,<field>,<field>,…` using the field names of [appearance-record.md](appearance-record.md); any subset of
columns; values are the *real* values (e.g. `NoseHeight=-3`), the module applies the bias and clamps to the range.
A row with `Id` `0` goes to the player currently on screen (F10 snapshot, change one slider, F11 finds him).

Imported rows are removed from the queue and copied to `faceai_done.csv`.

### New-world players

Players that the database does not contain have no appearance record. `faceai.lua` then **inserts** one: a copy of a
template player's record (optional `Template` column, default in the script) with the new id and the sliders, keeping
the table sorted by id and increasing the count. This needs room in the table (`fl26appcap`, 65,000 records).

**The `fl26regen` pack faces and how we get past them without a restart.** `fl26regen.dll` (source in FL Mod Studio, MIT)
keeps a list of the world's new players (`g_nlist`: per player a u32 id, an i16 pack-face index, a flag byte and a pad byte)
and, every 250 ms, copies the pack face over the appearance record of each player in it, also over a record we wrote. Its
lookup wrapper only answers for a player when the game's table has no record, so our record would win if it were not
overwritten. `faceai.lua` therefore finds that list in the DLL's own data (a pointer in the image to an ascending list of ids,
cross-checked against the players it manages) and sets the face index of the players it manages to -1; the DLL then leaves them
alone. It does this right before writing a record and again whenever the DLL rebuilds its list. The pack portrait, which the
DLL only redirects while the face index is >= 0, is redirected by `faceai.lua` itself. Nothing is written to the world file.
This was built from the DLL's source and checked against a fake process (`tests/check_release.py`); see the limits in the README.

## 5. Training the models

- Face: `python -m pesface train`. Training photos named `<player id>.<ext>` in `training/` are added with the player's
  current in-game values (from the latest dump) as labels.
- Hair: rules on a hair mask give length/curl/colour; a CLIP zero-shot step separates braids, locks, afro, mohawk,
  normal; the colour is mapped to the nearest of the seven presets after a brightness calibration fitted on the
  training photos. With ~40 labelled photos (hand-labelled in the *Haare* tab, or from dumps) a logistic-regression
  classifier on CLIP embeddings takes over for style, length, curl and the front/side/back options.
- Beard: CLIP on the lower face decides none / stubble / full beard. The game's own beard data for real-face players is
  placeholder, so it is not used for training.

Caveat for training data: players with a *real* face model keep default-ish appearance values. Use players where the
photo really matches the in-game look.

## 6. Reusing it elsewhere

- **Editor tools:** `data/layout.json` plus [appearance-record.md](appearance-record.md) are all you need to read or
  write these fields of an appearance record. The on-disk `PlayerAppearance.bin` (zlib container, 36-byte header after
  decompression, then 72-byte records) is *not* verified to use the same layout.
- **Mods/patches:** generate `faceai.csv` with this tool (or your own), ship it with `faceai.lua`.
- **Own tools:** call the Python functions directly, e.g. `from pesface.encoder import predict_all; predict_all("a.jpg")`
  returns a `{field: value}` dict.
