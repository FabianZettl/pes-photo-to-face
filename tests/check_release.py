"""faceai.lua must find fl26regen's list in a (fake) process, set face = -1 for the players it manages, leave others alone,
redirect the portrait and do it again after the DLL rebuilt its list. Needs luajit; skipped otherwise.
Run: python tests/check_release.py"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if not shutil.which("luajit"):
    print("release check skipped (luajit missing)")
    sys.exit(0)
with tempfile.TemporaryDirectory() as w:
    w = Path(w)
    (w / "content" / "faceai").mkdir(parents=True)
    (w / "content" / "faceai" / "faceai_done.csv").write_text("Id\r\n")
    # the module's Windows paths become forward slashes so that it runs here
    lua = (root / "sider" / "faceai.lua").read_text().replace("content\\\\faceai\\\\", "content/faceai/").replace("modules\\\\fl26world", "modules/fl26world")
    (w / "faceai.lua").write_text(lua)
    r = subprocess.run(["luajit", "-e", "ffi=nil", str(root / "tests" / "release_test.lua"), str(w / "faceai.lua"), str(w) + "/"],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    sys.exit(r.returncode)
