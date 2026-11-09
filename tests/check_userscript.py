"""The user script's page scraper against small HTML fixtures that imitate the sites (the real pages cannot be fetched
automatically, so these only prove the logic, not the real markup). Needs playwright + chromium; skipped otherwise.
Run: python tests/check_userscript.py"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("userscript check skipped (playwright missing)")
    sys.exit(0)
src = (root.parent / "userscript" / "fminside-to-pes-face-ai.user.js").read_text()
cases = [("transfermarkt-like.html", "transfermarkt", ("Ricky-Jade Jones", "FC St. Pauli", "2002-11-08")),
         ("sofifa-jsonld-like.html", "sofifa", ("Aleks Stojaković", "GNK Dinamo Zagreb", "2004-02-17")),
         ("sofifa-text-like.html", "sofifa", ("Mislav Ćutuk", "GNK Dinamo Zagreb", "2007-01-25"))]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    for f, site, want in cases:
        pg.goto((root / "fixtures" / f).as_uri())
        pg.evaluate("(s)=>{window.__PFA_TEST=true;window.__PFA_SITE=s}", site)
        pg.evaluate("(code)=>(0,eval)('var GM_xmlhttpRequest=()=>{};'+code)", src)
        d = pg.evaluate("()=>window.__pfaScrape()")
        assert (d["name"], d["team"], d["dob"]) == want, (f, d)
    b.close()
print("userscript scraper ok on", len(cases), "fixtures")
