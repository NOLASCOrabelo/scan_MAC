import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)
li_at = os.getenv("LINKEDIN_LI_AT")

JS = """
() => {
    function queryAllShadow(root, selector) {
        const found = [];
        try { found.push(...root.querySelectorAll(selector)); } catch(e) {}
        for (const el of root.querySelectorAll('*')) {
            if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
        }
        return found;
    }
    const mainFeed = document.querySelector('[data-testid="mainFeed"]');
    const searchRoot = mainFeed || document;
    let containers = Array.from(searchRoot.querySelectorAll('[role="listitem"]'));
    if (!containers.length) containers = Array.from(searchRoot.querySelectorAll('[data-display-contents="true"]'));
    if (!containers.length && mainFeed) containers = Array.from(mainFeed.children);
    if (!containers.length) containers = queryAllShadow(document, '[role="listitem"]');
    const samples = [];
    for (const c of containers.slice(0, 15)) {
        const txt = (c.innerText || c.textContent || '').trim();
        if (txt.length > 30) samples.push(txt.slice(0, 200));
        if (samples.length >= 5) break;
    }
    return { count: containers.length, samples };
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    ctx.add_cookies([{"name": "li_at", "value": li_at, "domain": ".www.linkedin.com", "path": "/"}])
    page = ctx.new_page()
    page.goto("https://www.linkedin.com/feed/")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(10)
    for _ in range(3):
        page.keyboard.press("PageDown")
        time.sleep(2)

    print("URL:", page.url)
    dados = page.evaluate(JS)
    print(f"Containers encontrados: {dados['count']}")
    for i, s in enumerate(dados["samples"]):
        print(f"  [{i+1}] {s[:150]}")
    browser.close()
