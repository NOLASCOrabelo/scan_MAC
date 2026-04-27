import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    context.add_cookies([{
        "name": "li_at",
        "value": LINKEDIN_LI_AT,
        "domain": ".www.linkedin.com",
        "path": "/"
    }])
    page = context.new_page()
    page.goto("https://www.linkedin.com/feed/")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(6)

    # Scroll para carregar posts
    for _ in range(3):
        page.keyboard.press("PageDown")
        time.sleep(2)

    # Salvar HTML
    html = page.content()
    with open("feed_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML salvo em feed_debug.html")

    # Testar seletores
    selectors = [
        'div[data-urn^="urn:li:activity:"]',
        'div[data-id^="urn:li:activity:"]',
        '.feed-shared-update-v2',
        '.occludable-update',
        '[data-view-name="feed-full-update"]',
        'article',
        '.scaffold-finite-scroll__content',
    ]
    for s in selectors:
        count = page.locator(s).count()
        print(f'  {s}: {count} elementos')

    browser.close()
