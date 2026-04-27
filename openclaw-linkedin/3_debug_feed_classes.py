import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    context.add_cookies([{"name": "li_at", "value": LINKEDIN_LI_AT, "domain": ".www.linkedin.com", "path": "/"}])
    page = context.new_page()
    page.goto("https://www.linkedin.com/feed/")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(5)
    
    page.keyboard.press("PageDown")
    time.sleep(3)
    
    try:
        main_html = page.locator("main").inner_html()
        with open("main_feed.html", "w", encoding="utf-8") as f:
            f.write(main_html)
        print("Salvo main_feed.html com sucesso!")
    except Exception as e:
        print(f"Erro: {e}")
        
    browser.close()
