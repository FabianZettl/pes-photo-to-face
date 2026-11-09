"""Photo -> hair guess (style/length/curl/colour) with simple, explainable rules on a hair mask.
Values use the game's codes (see data/layout.json). Rough on purpose: logical, not perfect."""
import os
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent.parent / "data" / "hair_segmenter.tflite"
STYLE = {"Normal": 1, "Trocken": 2, "Iro": 3, "Afro": 4, "Dreadlocks": 5, "Geflochten": 6, "Spezial": 7}
LENGTH = {"rasiert": 1, "Sehr kurz": 2, "Kurz": 3, "Mittel": 4, "Lang": 5}   # 1 and 2 follow from the menu order, not measured
# The game's seven hair colour presets (HairColourType 1..7) and their RGB values (read from the appearance dump,
# 99 % of all players use one of them), plus how common each is.
PRESETS = {1: (5, 4, 3), 2: (8, 5, 3), 3: (11, 7, 4), 4: (15, 8, 4), 5: (14, 10, 7), 6: (18, 14, 10), 7: (33, 28, 21)}
PRIOR = {1: .29, 2: .37, 3: .08, 4: .03, 5: .11, 6: .08, 7: .05}
CAL = Path(__file__).resolve().parent.parent / "data" / "hair_colour_cal.json"


def _preset_lab(rgb6):
    import cv2
    return cv2.cvtColor(np.uint8([[[min(255, c * 4) for c in rgb6]]]), cv2.COLOR_RGB2LAB)[0, 0].astype(float)


def colour_preset(stats):
    """stats = (darker-quartile L, a, b) of the hair pixels -> preset 1..7. Lighting shifts the whole photo, so L is
    mapped by a linear fit (data/hair_colour_cal.json, refit from the training photos) and warmth (a+b) decides
    between presets of similar brightness; the population share of each preset is a weak prior."""
    import json
    if stats is None:
        return 2
    cal = json.loads(CAL.read_text()) if CAL.exists() else {"alpha": 0.6, "beta": -2.0}
    L, a, b = stats
    Lg, warm = cal["alpha"] * L + cal["beta"], (a - 128) + (b - 128)
    best = None
    for k, rgb in PRESETS.items():
        pl = _preset_lab(rgb)
        sc = ((Lg - pl[0]) / 12) ** 2 + ((warm - ((pl[1] - 128) + (pl[2] - 128))) / 10) ** 2 - 0.6 * np.log(PRIOR[k])
        if best is None or sc < best[0]:
            best = (sc, k)
    return best[1]


def calibrate_colour(folder):
    """Refit the brightness mapping from photos named <player id> whose player has a colour preset (needs a dump)."""
    import cv2
    import json
    from .encoder import encode
    from .hairdata import decode
    T = decode()
    xs, ys = [], []
    for f in sorted(Path(folder).iterdir()):
        t = T.get(int(f.stem)) if f.stem.isdigit() else None
        if not t or t["HairColourType"] not in PRESETS or t["HairLength"] <= 1:   # shaved heads have no hair pixels
            continue
        try:
            _, box = encode(str(f), with_box=True)
        except ValueError:
            continue
        r = analyze(f, box)
        if r["_colstats"]:
            xs.append(r["_colstats"][0]); ys.append(_preset_lab(PRESETS[t["HairColourType"]])[0])
    if len(xs) < 8:
        print(f"Farbkalibrierung übersprungen: nur {len(xs)} brauchbare Fotos (ab 8)")
        return
    alpha, beta = np.polyfit(xs, ys, 1)
    alpha = float(np.clip(alpha, 0.2, 1.5))
    beta = float(np.mean(ys) - alpha * np.mean(xs))
    CAL.write_text(json.dumps({"alpha": alpha, "beta": beta, "n": len(xs)}))
    print(f"Haarfarbe kalibriert an {len(xs)} Fotos: L_Spiel = {alpha:.2f} * L_Foto + {beta:.1f}")


_seg = None
_clip = None
# Zero-shot hairstyle classes (CLIP) -> game style code. Trocken/Spezial have no visual definition we know, so no prompt.
CLIP_CLASSES = {
    "Geflochten": ["a close-up photo of a person with tight braids or cornrows", "a person with twists and braided hair"],
    "Dreadlocks": ["a close-up photo of a person with long dreadlocks"],
    "Afro": ["a close-up photo of a person with a large afro hairstyle", "a close-up photo of a person with short tightly curled hair"],
    "Iro": ["a close-up photo of a person with a mohawk hairstyle"],
    "Normal": ["a close-up photo of a person with short ordinary hair", "a close-up photo of a person with long loose wavy or straight hair",
               "a close-up photo of a person with a shaved head", "a close-up photo of a person with their hair tied back"],
}


def _load_clip():
    global _clip
    if _clip is None:
        from transformers import CLIPModel, CLIPProcessor
        _clip = (CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval(),
                 CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32"))
    return _clip


def hair_embedding(rgb, face, mask):
    """CLIP embedding of the hair region only (bounding box of the hair mask around the head, a little padding), so the
    classifier sees the hair and not the face. Falls back to the head crop when there is hardly any hair in the mask."""
    import torch
    from PIL import Image
    model, proc = _load_clip()
    H, W = rgb.shape[:2]
    x, y, w, h = face
    x0, x1, y0, y1 = max(0, int(x - 0.8 * w)), min(W, int(x + 1.8 * w)), max(0, int(y - 1.1 * h)), min(H, int(y + 1.3 * h))
    ys, xs = np.where(mask[y0:y1, x0:x1])
    if len(ys) < 200:
        box = (max(0, int(x - 0.7 * w)), max(0, int(y - 1.0 * h)), min(W, int(x + 1.7 * w)), min(H, int(y + 1.2 * h)))
    else:
        pad = int(0.05 * max(w, h))
        box = (max(0, x0 + xs.min() - pad), max(0, y0 + ys.min() - pad), min(W, x0 + xs.max() + pad), min(H, y0 + ys.max() + pad))
    with torch.no_grad():
        e = model.get_image_features(**proc(images=Image.fromarray(rgb[box[1]:box[3], box[0]:box[2]]), return_tensors="pt"))[0].numpy()
    return e / np.linalg.norm(e)


def _clip_probs(crop, prompts):
    """Softmax over free-text prompts for a PIL image (loads CLIP once)."""
    global _clip
    import torch
    from transformers import CLIPModel, CLIPProcessor
    if _clip is None:
        _clip = (CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval(),
                 CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32"))
    model, proc = _clip
    inp = proc(text=prompts, images=crop, return_tensors="pt", padding=True)
    with torch.no_grad():
        return model(**inp).logits_per_image.softmax(-1)[0].numpy()


BEARD = ["a close-up photo of a clean-shaven face without any facial hair",
         "a close-up photo of a face with light stubble",
         "a close-up photo of a face with a full thick beard"]


def beard_level(rgb, face):
    """0 = clean-shaven, 1 = stubble, 2 = full beard (CLIP on the lower half of the face; the game's own beard data of
    real-face players is placeholder, so the learned beard guess from the embedding was far too bold)."""
    from PIL import Image
    H, W = rgb.shape[:2]
    x, y, w, h = face
    crop = Image.fromarray(rgb[max(0, int(y + 0.45 * h)):min(H, int(y + 1.15 * h)), max(0, int(x - 0.1 * w)):min(W, int(x + 1.1 * w))])
    return int(np.argmax(_clip_probs(crop, BEARD)))


def clip_style(rgb, face):
    """-> ({style name: probability}, image embedding) of the head crop; classes with several prompts take the best prompt."""
    global _clip
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
    if _clip is None:
        _clip = (CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval(),
                 CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32"))
    model, proc = _clip
    H, W = rgb.shape[:2]
    x, y, w, h = face
    box = (max(0, int(x - 0.7 * w)), max(0, int(y - 1.0 * h)), min(W, int(x + 1.7 * w)), min(H, int(y + 1.2 * h)))
    crop = Image.fromarray(rgb[box[1]:box[3], box[0]:box[2]])
    prompts = [(k, t) for k, ts in CLIP_CLASSES.items() for t in ts]
    inp = proc(text=[t for _, t in prompts], images=crop, return_tensors="pt", padding=True)
    with torch.no_grad():
        o = model(**inp)
        p = o.logits_per_image.softmax(-1)[0].numpy()
        emb = o.image_embeds[0].numpy()
        emb = emb / np.linalg.norm(emb)
    out = {}
    for (k, _), v in zip(prompts, p):
        out[k] = max(out.get(k, 0.0), float(v))
    z = sum(out.values())
    return {k: v / z for k, v in out.items()}, emb


SEG_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/hair_segmenter/float32/latest/hair_segmenter.tflite"


def _mask(rgb):
    global _seg
    if not MODEL.exists():
        import urllib.request
        urllib.request.urlretrieve(SEG_URL, MODEL)   # Google MediaPipe hair segmenter, Apache-2.0
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    if _seg is None:
        _seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=mpt.BaseOptions(model_asset_path=str(MODEL)), output_category_mask=True))
    out = _seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    return np.squeeze(out.category_mask.numpy_view()) == 1


def analyze(img_path, face, use_model=True):
    """face = (x, y, w, h) of the detected face. Returns dict of hair values plus the features used."""
    rgb = cv2.cvtColor(cv2.imread(str(img_path)), cv2.COLOR_BGR2RGB)
    m = _mask(rgb)
    H, W = m.shape
    x, y, w, h = face

    def cov(x0, x1, y0, y1):   # share of hair pixels in a box (clipped to the image)
        x0, x1, y0, y1 = max(0, int(x0)), min(W, int(x1)), max(0, int(y0)), min(H, int(y1))
        return float(m[y0:y1, x0:x1].mean()) if x1 > x0 and y1 > y0 else 0.0

    top = cov(x, x + w, y - 0.45 * h, y + 0.15 * h)            # above / on the forehead
    side = (cov(x - 0.4 * w, x, y + 0.1 * h, y + 0.6 * h) + cov(x + w, x + 1.4 * w, y + 0.1 * h, y + 0.6 * h)) / 2
    below = (cov(x - 0.4 * w, x + 0.1 * w, y + h, y + 1.4 * h) + cov(x + 0.9 * w, x + 1.4 * w, y + h, y + 1.4 * h)) / 2
    cols = np.where(m[max(0, int(y - 0.6 * h)):int(y + 0.6 * h)].any(0))[0]
    spread = (cols.max() - cols.min()) / w if len(cols) else 0.0   # hair width relative to the face
    core = cov(x + 0.3 * w, x + 0.7 * w, y - 0.45 * h, y + 0.05 * h)   # centre strip on top
    outer = (cov(x, x + 0.25 * w, y - 0.3 * h, y + 0.05 * h) + cov(x + 0.75 * w, x + w, y - 0.3 * h, y + 0.05 * h)) / 2

    if top < 0.12:
        length = "rasiert"
    elif below > 0.25:
        length = "Lang"
    elif top < 0.3 and side < 0.15:
        length = "Sehr kurz"
    elif side > 0.3:
        length = "Mittel"
    else:
        length = "Kurz"

    # curl: how ragged the hair outline is and how much fine texture lies inside it
    mm = m.astype(np.uint8)
    cnts, _ = cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    per, area = sum(cv2.arcLength(c, True) for c in cnts), max(1, int(mm.sum()))
    rough = per / (2 * np.sqrt(np.pi * area))                        # 1 = smooth blob
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    er = cv2.erode(mm, np.ones((9, 9), np.uint8)).astype(bool)
    tex = float(np.abs(cv2.Laplacian(gray, cv2.CV_32F))[er].mean()) if er.any() else 0.0
    curl = int(np.clip(round((rough - 2.0) + (tex - 8) / 12), 0, 6)) if length != "rasiert" else 0

    pr, emb = clip_style(rgb, face)
    locks = pr["Geflochten"] + pr["Dreadlocks"]          # braids and dreadlocks look alike to CLIP: decide by length
    if length == "rasiert":
        style = "Normal"
    elif locks >= 0.5:
        style = "Dreadlocks" if length == "Lang" else "Geflochten"
    elif pr["Afro"] >= 0.35:
        style = "Afro"
    elif pr["Iro"] >= 0.5 and outer < 0.3:
        style = "Iro"
    else:
        style = "Normal"
    # the game's own data: braids, locks and afros are always strongly curled
    curl = max(curl, {"Geflochten": 5, "Dreadlocks": 5, "Afro": 4}.get(style, 0))

    px = rgb[er] if er.any() else rgb[m]
    if len(px) and length != "rasiert":
        L3 = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(float)
        stats = (float(np.percentile(L3[:, 0], 25)), float(np.median(L3[:, 1])), float(np.median(L3[:, 2])))
    else:
        stats = None
    guess = {"HairStyle": STYLE[style], "HairLength": LENGTH[length], "HairCurl": curl}
    rules = dict(guess)
    emb2 = hair_embedding(rgb, face, m)
    if use_model:
        from . import hairmodel
        guess.update(hairmodel.predict(emb, emb2, guess))
    preset = colour_preset(stats)
    col = np.array(PRESETS[preset])
    return {**guess, "_colstats": stats, "HairColourType": preset,
            "HairColourR": int(col[0]), "HairColourG": int(col[1]), "HairColourB": int(col[2]),
            "_emb": emb, "_emb2": emb2, "_rules": rules, "_why": dict(clip={k: round(v, 2) for k, v in pr.items()}, style=style, length=length, top=round(top, 2), side=round(side, 2), below=round(below, 2),
                         spread=round(spread, 2), core=round(core, 2), outer=round(outer, 2), rough=round(float(rough), 2), tex=round(tex, 1))}
