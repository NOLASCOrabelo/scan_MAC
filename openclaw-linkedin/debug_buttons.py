import os, time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import sys

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()
li_at = os.getenv('LINKEDIN_LI_AT')

JS_DUMP = '''
() => {
    function queryAllShadow(root, selector) {
        const found = [];
        try { found.push(...root.querySelectorAll(selector)); } catch(e) {}
        for (const el of root.querySelectorAll('*')) {
            if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
        }
        return found;
    }
    const btns = queryAllShadow(document, 'button, [role="button"]');
    return btns.map(b => ({
        tag: b.tagName,
        ariaLabel: b.getAttribute('aria-label'),
        text: b.innerText ? b.innerText.trim().replace(/\\n/g, ' ') : ''
    })).filter(b => b.text || b.ariaLabel);
}
'''

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    context.add_cookies([{'name': 'li_at', 'value': li_at, 'domain': '.www.linkedin.com', 'path': '/'}])
    page = context.new_page()
    page.goto('https://www.linkedin.com/feed/')
    page.wait_for_load_state('domcontentloaded')
    time.sleep(10)
    data = page.evaluate(JS_DUMP)
    for d in data:
        t = (d.get('text') or '').lower()
        a = (d.get('ariaLabel') or '').lower()
        if any(k in t or k in a for k in ['curtir', 'like', 'comentar', 'comment', 'gostei']):
            print(f"Tag: {d.get('tag')}, aria: {d.get('ariaLabel')}, text: {d.get('text')}")
    browser.close()
