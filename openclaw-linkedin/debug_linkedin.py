import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")

def debug_linkedin():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies([{
            "name": "li_at",
            "value": LINKEDIN_LI_AT,
            "domain": ".www.linkedin.com",
            "path": "/"
        }])

        page = context.new_page()
        page.goto("https://www.linkedin.com/feed/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(5)
        
        html = page.content()
        with open("linkedin_feed_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("HTML salvo com sucesso.")
        browser.close()

if __name__ == "__main__":
    debug_linkedin()
