# Appearance record layout

Verified against the in-memory `PlayerAppearance` table of an eFootball PES 2021 SEASON UPDATE based build (Football Life 2027).
One record is **72 bytes (576 bits)**. Bytes 0-3 are the player id (u32, little endian). All other fields are bit fields, counted **LSB first** (bit *n* = byte *n // 8*, bit *n % 8*). A field stores `value + bias`.

| Field | First bit | Width | Stored = value + | Value range | Evidence |
|---|---|---|---|---|---|
| `HeadLength` | 140 | 4 | 7 | -7 … 7 | statistical match with 44 % of ~9,000 players (slider CSV) |
| `HeadWidth` | 144 | 4 | 7 | -7 … 7 | statistical match with 46 % of ~9,000 players (slider CSV) |
| `HeadDepth` | 148 | 4 | 7 | -7 … 7 | statistical match with 49 % of ~9,000 players (slider CSV) |
| `Jawline` | 180 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `JawHeight` | 184 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `Cheekbones` | 192 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `BrowWidth` | 212 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `InnerEyebrowHeight` | 216 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `TempleWidth` | 224 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `OuterEdyebrowHeight` | 228 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `EyebrowDepth` | 232 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `PupilSize` | 236 | 4 | 7 | -7 … 7 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `EyeDepth` | 240 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `InnerEyePosition` | 244 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `InnerEyeHeight` | 248 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `OuterEyePosition` | 252 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `EyeCornerHeight` | 256 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `UpperEyelidWd.(Inner)` | 260 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `UpperEyelidHt.(Inner)` | 264 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `UpperEyelidWd.(Outer)` | 268 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `UpperEyelidHt.(Outer)` | 272 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `BottomEyelidHeight` | 280 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `HorizontalEyePosition` | 284 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `EyeHeight` | 288 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `NoseHeight` | 292 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `NoseTipDepth` | 296 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `NostrilWidth` | 300 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `NoseDepth` | 308 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `NoseWidth` | 312 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `MouthPosition` | 320 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `MouthDepth` | 324 | 4 | 7 | -5 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `LipSize` | 328 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `MouthCornerHeight` | 336 | 4 | 7 | -7 … 7 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `LipWidth` | 340 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `ChinWidth` | 348 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `ChinHeight` | 352 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `ChinDepth` | 356 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `SkinColour` | 360 | 3 | 0 | 1 … 6 | statistical match with 85 % of ~9,000 players (slider CSV) |
| `CheekType` | 363 | 3 | -1 | 1 … 6 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `Forehead` | 368 | 3 | -1 | 1 … 7 | statistical match with 85 % of ~9,000 players (slider CSV) |
| `FacialHairType` | 371 | 5 | 0 | 0 … 19 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `LaughterLines` | 376 | 3 | -1 | 1 … 5 | statistical match with 80 % of ~9,000 players (slider CSV) |
| `UpperEyelidType` | 379 | 3 | 0 | 1 … 7 | statistical match with 64 % of ~9,000 players (slider CSV) |
| `BottomEyelidType` | 384 | 3 | -1 | 1 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `EarLength` | 388 | 4 | 7 | -7 … 7 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `EarWidth` | 392 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `EarAngle` | 396 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `EyebrowType` | 400 | 3 | -1 | 1 … 8 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `NeckLineType` | 405 | 2 | -1 | 1 … 4 | statistical match with 87 % of ~9,000 players (slider CSV) |
| `FaceSize` | 408 | 4 | 7 | -7 … 7 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `FaceHeight` | 412 | 4 | 7 | -7 … 7 | statistical match with 95 % of ~9,000 players (slider CSV) |
| `NoseType` | 416 | 3 | -1 | 1 … 8 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `UpperLipType` | 424 | 3 | -1 | 1 … 5 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `LowerLipType` | 427 | 3 | -1 | 1 … 5 | statistical match with 98 % of ~9,000 players (slider CSV) |
| `HairColourR` | 430 | 6 | 0 | 0 … 63 | measured in Edit mode (change one option, diff the dump) |
| `HairColourG` | 436 | 6 | 0 | 0 … 63 | measured in Edit mode (change one option, diff the dump) |
| `HairColourB` | 442 | 6 | 0 | 0 … 63 | measured in Edit mode (change one option, diff the dump) |
| `HairStyle` | 448 | 3 | 0 | 0 … 7 | measured in Edit mode (change one option, diff the dump) |
| `EyebrowColourR` | 456 | 6 | 0 | 0 … 63 | statistical match with 98 % of ~9,000 players (slider CSV) |
| `EyebrowStyle` | 462 | 2 | 0 | 0 … 2 | statistical match with 96 % of ~9,000 players (slider CSV) |
| `EyebrowColourG` | 464 | 6 | 0 | 0 … 63 | statistical match with 98 % of ~9,000 players (slider CSV) |
| `EyebrowDensity` | 470 | 2 | 0 | 0 … 3 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `EyebrowColourB` | 472 | 6 | 0 | 0 … 63 | statistical match with 98 % of ~9,000 players (slider CSV) |
| `EyebrowThickness` | 478 | 2 | 0 | 0 … 2 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `HairLength` | 480 | 3 | 0 | 0 … 5 | measured in Edit mode (change one option, diff the dump) |
| `HairCurl` | 483 | 3 | 1 | 0 … 6 | measured in Edit mode (change one option, diff the dump) |
| `FacialHairColourR` | 492 | 6 | 0 | 0 … 63 | statistical match with 98 % of ~9,000 players (slider CSV) |
| `FacialHairColourG` | 498 | 6 | 0 | 0 … 63 | statistical match with 98 % of ~9,000 players (slider CSV) |
| `FacialHairColourB` | 504 | 6 | 0 | 0 … 63 | statistical match with 99 % of ~9,000 players (slider CSV) |
| `Thickness` | 510 | 2 | 0 | 0 … 3 | statistical match with 97 % of ~9,000 players (slider CSV) |
| `IrisColour` | 512 | 4 | -1 | 1 … 11 | statistical match with 90 % of ~9,000 players (slider CSV) |
| `HairColourType` | 524 | 3 | 0 | 0 … 7 | measured in Edit mode (change one option, diff the dump) |
| `HairFront` | 528 | 2 | 0 | 1 … 3 | measured in Edit mode (change one option, diff the dump) |
| `HairParting` | 531 | 3 | 0 | 1 … 6 | measured in Edit mode (change one option, diff the dump) |
| `HairBack` | 534 | 3 | 0 | 1 … 4 | measured in Edit mode (change one option, diff the dump) |
| `HairHairline` | 537 | 2 | 0 | 1 … 3 | measured in Edit mode (change one option, diff the dump) |
| `HairForehead` | 540 | 2 | 0 | 1 … 3 | measured in Edit mode (change one option, diff the dump) |

Bits not listed are unused or unknown (about 290 bits, mostly body/other fields).

## Value meanings

**HairStyle** (3 bit): 1 Normal, 2 Trocken (dry), 3 Iro (mohawk), 4 Afro, 5 Dreadlocks, 6 Geflochten (braids), 7 Spezial. 5-7 follow from the menu order, 1-4 were measured.

**HairLength**: 5 Lang, 4 Mittel, 3 Kurz were measured; 2 Sehr kurz and 1 rasiert follow from the menu order.

**HairCurl**: stored value = curl + 1 (curl 0..6).

**HairFront** (Vorne Stil): 1 Hoch, 2 Hängend, 3 Zurückgekämmt. **HairParting**: 1 Aus, 2 Links 2, 4 Mitte measured; 3 Links 1, 5 Rechts 1, 6 Rechts 2 inferred. **HairHairline**: Modell 1-3 = 1-3. **HairForehead**: 1 Eng, 2 Normal measured; 3 Weit inferred. **HairBack** (Seite/Hinten): 1 Normal, 2 Weniger Volumen, 3 Kürzere Seiten, 4 Kurzgeschnitten.

**HairColourType** 1-7 are the game's colour presets, 0 means a custom colour. The preset RGB values (6 bit per channel, 0-63) are stored in `HairColourR/G/B` as well:

| Type | R | G | B |
|---|---|---|---|
| 1 | 5 | 4 | 3 |
| 2 | 8 | 5 | 3 |
| 3 | 11 | 7 | 4 |
| 4 | 15 | 8 | 4 |
| 5 | 14 | 10 | 7 |
| 6 | 18 | 14 | 10 |
| 7 | 33 | 28 | 21 |

## Weak fields

`HeadLength`, `HeadWidth`, `HeadDepth`, `UpperEyelidType` and `LaughterLines` match the reference data only loosely (44-64 %). The positions are the best candidates, not proven.
