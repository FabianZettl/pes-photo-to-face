import os
os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")  # deepface needs keras 2 (tf-keras)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")


def encode(img_path, with_box=False):
    """128-d Facenet embedding of the largest face in the image (the detector sometimes adds a false second one)."""
    from deepface import DeepFace
    reps = None
    for det in ("opencv", "retinaface"):   # retinaface is slower but finds tilted and half-turned faces
        try:
            reps = DeepFace.represent(img_path, model_name="Facenet", detector_backend=det, enforce_detection=True)
            break
        except ValueError:
            continue
    if not reps:
        raise ValueError("kein Gesicht gefunden")
    r = max(reps, key=lambda r: r["facial_area"]["w"] * r["facial_area"]["h"])
    if with_box:
        a = r["facial_area"]
        return r["embedding"], (a["x"], a["y"], a["w"], a["h"])
    return r["embedding"]


def predict_all(img_path):
    """Face sliders (from the embedding) + hair guess (from the photo) as one {column: value} dict."""
    from . import hair, model
    emb, box = encode(img_path, with_box=True)
    vals = model.predict(emb)
    vals.update({k: v for k, v in hair.analyze(img_path, box).items() if not k.startswith("_")})
    # beard: decided from the photo; unknown beard types stay conservative (no beard / stubble / one full-beard type)
    import cv2
    level = hair.beard_level(cv2.cvtColor(cv2.imread(str(img_path)), cv2.COLOR_BGR2RGB), box)
    vals["FacialHairType"] = (0, 1, 6)[level]
    if level == 0:
        vals.pop("Thickness", None)   # no beard: leave the template's value alone
    else:
        vals["Thickness"] = (0, 1, 3)[level]
    return vals


def photo_warnings(img_path):
    """Hints about photos that are too small for a reliable guess."""
    import cv2
    im = cv2.imread(str(img_path))
    _, box = encode(img_path, with_box=True)
    out = []
    if min(im.shape[:2]) < 500:
        out.append(f"Foto klein ({im.shape[1]}x{im.shape[0]} px): ab 800 px Kantenlänge wird die Schätzung deutlich besser")
    if box[2] < 200:
        out.append(f"Gesicht nur {box[2]} px breit: Haare, Bart und Hautton sind dann unsicher")
    return out
