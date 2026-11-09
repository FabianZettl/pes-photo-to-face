"""The fingerprint of fl26playerids.json must be identical in Python (pesface/newworld.py) and Lua (sider/faceai.lua):
the tool writes it, the Sider module checks it. Needs luajit for the Lua half. Run: python tests/check_fingerprint.py"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pesface.newworld import fingerprint

# CRLF line ends are in here on purpose: Mod Studio's JSON has them and the Sider module must read the file binary
data = bytes(range(256)) * 40 + b"fl26playerids\r\n{}\r\n"
py = fingerprint(data)
if shutil.which("luajit"):
    lua = ("local h = 0; local d = io.read('*a'); for i = 1, #d do h = (h * 31 + d:byte(i)) % 4294967296 end; io.write(string.format('%d', h))")
    out = subprocess.run(["luajit", "-e", lua], input=data, capture_output=True).stdout.decode()
    assert out == str(py), (out, py)
    print("fingerprint ok (python == lua):", py)
else:
    print("fingerprint computed (luajit missing, Lua half not checked):", py)
