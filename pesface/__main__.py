import os
import sys
from . import model

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "eval":
    r = model.evaluate()
    for n, (e, b) in sorted(r.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        print(f"{n:24s} model {e:.2f}  baseline {b:.2f}  gain {100*(1-e/b):5.1f}%")
    print("mean gain %.1f%%" % (100 * sum(1 - e / b for e, b in r.values()) / len(r)))
elif cmd == "train":
    model.train()
elif cmd == "predict":  # python -m pesface predict photo.jpg [player_id]  -> face_<id>.csv
    from .encoder import predict_all
    pid = sys.argv[3] if len(sys.argv) > 3 else "0"
    vals = predict_all(sys.argv[2])
    for k, v in vals.items():
        print(f"{k:24s}{v}")
    with open(f"face_{pid}.csv", "w", newline="") as f:
        model.to_csv([(pid, vals)], f)
elif cmd == "queue":  # python -m pesface queue <foto|ordner>...   file name (without extension) = player id
    from pathlib import Path
    from .encoder import predict_all
    files = [f for a in sys.argv[2:] for f in (sorted(Path(a).iterdir()) if Path(a).is_dir() else [Path(a)])
             if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    for f in files:
        try:
            n = model.queue(f.stem, predict_all(str(f)))
            print(f"{f.name}: queued as {f.stem} ({n} in queue)")
        except ValueError as e:
            print(f"{f.name}: skipped - {e}")
elif cmd == "players":  # python -m pesface players <players_dump.bin> <appearance_mem_NN.bin> <pesdb-folder>
    print(model.build_players(*sys.argv[2:5]), "players")
elif cmd == "evalhair":  # python -m pesface evalhair training
    from . import hairdata
    hairdata.evaluate(sys.argv[2])
elif cmd == "trainhair":  # python -m pesface trainhair training
    from . import hairmodel
    hairmodel.train(sys.argv[2])
elif cmd == "calhaircolour":  # python -m pesface calhaircolour training
    from . import hair
    hair.calibrate_colour(sys.argv[2])
elif cmd == "fetch-base-data":   # base training data of the original project (no licence: we do not redistribute it)
    import urllib.request
    for f in ("data-cleaned.csv", "encodings.json"):
        urllib.request.urlretrieve("https://raw.githubusercontent.com/AlirezaF80/PES-Edit-Face-AI/main/" + f, model.DATA / f)
        print("geladen:", f)
elif cmd == "serve":
    import uvicorn
    uvicorn.run("pesface.server:app", port=int(os.environ.get("PESFACE_PORT", 8000)))
else:
    sys.exit("usage: python -m pesface eval|train|predict <photo> [id]|queue <photo|dir>...|players <dump> <appearance> <pesdb>|fetch-base-data|serve")
