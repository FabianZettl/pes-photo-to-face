"""Licence filter and author cleanup of pesface/commons.py (no network). Run: python tests/check_commons.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pesface.commons import clean_author, license_ok

for ok in ("CC BY 4.0", "CC BY-SA 3.0", "CC BY-SA 2.0 de", "CC0", "Public domain", "PD-old", "CC-BY-SA-4.0"):
    assert license_ok(ok), ok
for bad in ("CC BY-NC 4.0", "CC BY-ND 2.0", "Fair use", "?", "", None, "All rights reserved", "FAL"):
    assert not license_ok(bad), bad
assert clean_author('<a href="//x">Jane &amp; Co</a>') == "Jane & Co"
assert clean_author("") == "unbekannt"
print("commons ok")
