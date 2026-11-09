"""Every click on the user script's button must end in something visible (button state + toast), also when things go
wrong. GM_xmlhttpRequest is stubbed per scenario. Needs playwright + chromium; skipped otherwise.
Run: python tests/check_userscript_feedback.py"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("userscript feedback check skipped (playwright missing)")
    sys.exit(0)
src = (root.parent / "userscript" / "fminside-to-pes-face-ai.user.js").read_text()

STUB = """(scenario) => {
  window.__PFA_SITE = 'transfermarkt'; window.__PFA_WATCHDOG = 600;
  window.GM_xmlhttpRequest = (o) => {
    if (scenario === 'hang') return;                                   // nothing ever comes back
    if (o.method === 'GET') return setTimeout(() => o.onload({status: 200, response: new Blob([new Uint8Array(2000)])}), 20);
    if (scenario === 'down') return setTimeout(() => o.onerror(), 20);   // tool not running
    if (scenario === 'html') return setTimeout(() => o.onload({status: 404, responseText: '<html>nope</html>'}), 20);
    const best = [{name: 'Test Player', score: 1}];
    setTimeout(() => o.onload({status: 200, responseText: JSON.stringify(scenario === 'auto' ? {auto: true, best} : {best})}), 20);
  };
}"""
cases = [("auto", "✔", False), ("inbox", "✔", False), ("down", "✖", True), ("html", "✖", True), ("hang", "✖", True)]
with sync_playwright() as p:
    b = p.chromium.launch()
    for scenario, mark, bad in cases:
        pg = b.new_page()
        pg.goto((root / "fixtures" / "transfermarkt-like.html").as_uri())
        pg.evaluate(STUB, scenario)
        pg.evaluate("(code)=>(0,eval)(code)", src)
        pg.click("button")
        assert "sendet" in pg.inner_text("button"), (scenario, "no busy state")
        pg.wait_for_function(f"document.querySelector('button').textContent.includes('{mark}')", timeout=4000)
        toast = pg.locator("#pfa-toast")
        assert toast.count() == 1 and toast.inner_text().strip(), (scenario, "no toast")
        red = "185, 28, 28" in toast.evaluate("e=>getComputedStyle(e).backgroundColor")
        assert red == bad, (scenario, "toast colour", red)
        print("ok:", scenario, "->", pg.inner_text("button"), "|", toast.inner_text()[:60])
        pg.close()
    # no name on the page: the old script stayed silent here
    pg = b.new_page(); pg.set_content("<html><body><p>empty</p></body></html>")
    pg.evaluate(STUB, "auto"); pg.evaluate("(code)=>(0,eval)(code)", src); pg.click("button")
    pg.wait_for_function("document.querySelector('button').textContent.includes('✖')", timeout=4000)
    print("ok: no name ->", pg.locator("#pfa-toast").inner_text()[:60])
    b.close()
print("userscript feedback ok")
