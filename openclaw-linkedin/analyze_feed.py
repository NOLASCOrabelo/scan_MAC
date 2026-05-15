"""
analyze_feed.py
Captura o HTML real do feed do LinkedIn e identifica os seletores CSS disponíveis.
Tenta renovar o cookie automaticamente se estiver expirado.

Uso: python analyze_feed.py
"""
import os
import time
from dotenv import load_dotenv, set_key
from playwright.sync_api import sync_playwright

load_dotenv()

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "feed_live_debug.html")

SELECTORS_TO_TEST = [
    'div[data-urn^="urn:li:activity:"]',
    'div[data-id^="urn:li:activity:"]',
    'div[data-entity-urn^="urn:li:activity:"]',
    '.feed-shared-update-v2',
    '.occludable-update',
    '[data-view-name="feed-full-update"]',
    '[data-view-name="feed-index-segment-entity"]',
    '.scaffold-finite-scroll__content > div > div',
    'article',
    '.main-feed-activity-card',
    '.feed-shared-update',
]

TEXT_SELECTORS = [
    '.update-components-text',
    '.feed-shared-update-v2__description',
    '.feed-shared-inline-show-more-text',
    '[data-test-id="main-feed-activity-card__commentary"]',
    '.break-words',
    'span[dir="ltr"]',
]

AUTHOR_SELECTORS = [
    '.update-components-actor__name',
    '.feed-shared-actor__name',
    '.update-components-actor__title',
    '.feed-shared-actor__title',
]


def get_cookie():
    load_dotenv(override=True)
    return os.getenv("LINKEDIN_LI_AT")


def run_analysis():
    li_at = get_cookie()
    if not li_at:
        print("[ERRO] LINKEDIN_LI_AT não definido no .env")
        return

    print("=" * 55)
    print("  LinkedIn Feed Analyzer")
    print("=" * 55)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        context.add_cookies([{
            "name": "li_at",
            "value": li_at,
            "domain": ".www.linkedin.com",
            "path": "/",
        }])

        page = context.new_page()

        print("\n[1/4] Acessando feed...")
        page.goto("https://www.linkedin.com/feed/")
        try:
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        time.sleep(10)

        current_url = page.url
        print(f"      URL: {current_url}")

        # Cookie expirado?
        if "login" in current_url or "authwall" in current_url:
            print("\n[AVISO] Cookie expirado. Tentando renovar automaticamente...")
            browser.close()

            try:
                from refresh_cookie import refresh
                if refresh():
                    li_at = get_cookie()
                    print("[OK] Cookie renovado. Reiniciando análise...\n")
                    run_analysis()
                else:
                    print("[ERRO] Não foi possível renovar o cookie automaticamente.")
                    print("       Preencha LINKEDIN_EMAIL e LINKEDIN_PASSWORD no .env")
            except Exception as e:
                print(f"[ERRO] Falha ao renovar cookie: {e}")
            return

        print("\n[2/4] Scrollando para carregar posts...")
        for _ in range(4):
            page.keyboard.press("PageDown")
            time.sleep(2)

        # Salvar HTML
        html = page.content()
        with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"      HTML salvo em: {OUTPUT_HTML}")

        print("\n[3/4] Testando seletores de container de posts:")
        working_container = None
        for sel in SELECTORS_TO_TEST:
            count = page.locator(sel).count()
            status = f"✓ {count} elementos" if count > 0 else "✗ 0"
            print(f"  {status:20} {sel}")
            if count > 0 and not working_container:
                working_container = (sel, count)

        print("\n[4/4] Testando seletores de texto e autor:")
        if working_container:
            sel, count = working_container
            print(f"\n  Usando container: {sel} ({count} posts)")
            first_post = page.locator(sel).first

            print("\n  Seletores de TEXTO:")
            for ts in TEXT_SELECTORS:
                c = first_post.locator(ts).count()
                if c > 0:
                    sample = first_post.locator(ts).first.inner_text().strip()[:80]
                    print(f"  ✓ {ts}")
                    print(f"    → \"{sample}\"")
                else:
                    print(f"  ✗ {ts}")

            print("\n  Seletores de AUTOR:")
            for as_ in AUTHOR_SELECTORS:
                c = first_post.locator(as_).count()
                if c > 0:
                    sample = first_post.locator(as_).first.inner_text().strip()[:60]
                    print(f"  ✓ {as_}")
                    print(f"    → \"{sample}\"")
                else:
                    print(f"  ✗ {as_}")
        else:
            print("  Nenhum container encontrado. Verifique o feed_live_debug.html")

        browser.close()

    print("\n" + "=" * 55)
    print("  Análise concluída!")
    if working_container:
        print(f"  Seletor recomendado: {working_container[0]}")
    print("=" * 55)


if __name__ == "__main__":
    run_analysis()
