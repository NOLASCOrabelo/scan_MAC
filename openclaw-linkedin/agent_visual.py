"""
agent_visual.py
Versão do agente com navegador VISÍVEL para debug.
Rode localmente: python agent_visual.py
"""
import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")
LLM_API_KEY = os.getenv("LLM_API_KEY")

with open("instructions.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

client = genai.Client(api_key=LLM_API_KEY)
MODEL = "gemini-3.1-flash-lite-preview"

print("=" * 50)
print("  OpenClaw LinkedIn Agent (VISUAL DEBUG)")
print("=" * 50)

with sync_playwright() as p:
    print("\n[1/3] Abrindo navegador VISÍVEL...")
    browser = p.chromium.launch(headless=False, slow_mo=1000)  # slow_mo para ver as ações
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    context.add_cookies([{
        "name": "li_at",
        "value": LINKEDIN_LI_AT,
        "domain": ".www.linkedin.com",
        "path": "/",
    }])

    page = context.new_page()

    print("[2/3] Acessando feed...")
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    time.sleep(10)

    print("[3/3] Tentando reagir ao primeiro post...")
    
    # Marcar o primeiro post
    page.evaluate("""
    () => {
        const mainFeed = document.querySelector('[data-testid="mainFeed"]');
        const searchRoot = mainFeed || document;
        let containers = Array.from(searchRoot.querySelectorAll('[role="listitem"]'));
        if (!containers.length) containers = Array.from(searchRoot.querySelectorAll('[data-display-contents="true"]'));
        if (!containers.length && mainFeed) containers = Array.from(mainFeed.children);
        const valid = containers.filter(c => (c.innerText||'').trim().length > 30);
        if (valid[0]) valid[0].setAttribute('data-kiro-test-post', '0');
    }
    """)
    
    # Usar Playwright locator para clicar de verdade
    container = page.locator('[data-kiro-test-post="0"]')
    
    reaction_keywords = ['like', 'curtir', 'celebrate', 'support', 'love']
    clicked = False
    
    for keyword in reaction_keywords:
        try:
            btn = container.locator(f'button[aria-label*="{keyword}" i]').first
            if btn.count() > 0:
                print(f"  Clicando no botão: {keyword}")
                btn.click(timeout=5000)
                clicked = True
                print(f"  ✅ Clique executado com sucesso!")
                break
        except Exception as e:
            print(f"  ⚠️  Falha ao clicar em '{keyword}': {e}")
            continue
    
    if not clicked:
        print("  ❌ Nenhum botão de reação encontrado")
    
    print("\n⏸️  Navegador vai ficar aberto por 30s para você verificar visualmente.")
    print("   Veja se a reação apareceu no post!")
    time.sleep(30)

    browser.close()

print("\n✅ Teste concluído. Verifique se a reação apareceu no LinkedIn.")
