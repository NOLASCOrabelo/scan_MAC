"""
refresh_cookie.py
Faz login no LinkedIn com usuário/senha e atualiza o li_at no .env automaticamente.

Uso: python refresh_cookie.py
"""
import os
import re
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL = os.getenv("LINKEDIN_EMAIL")
PASSWORD = os.getenv("LINKEDIN_PASSWORD")
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def update_env(key: str, value: str):
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf"^{key}=.*$"
    new_line = f"{key}={value}"

    if re.search(pattern, content, flags=re.MULTILINE):
        content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        content += f"\n{new_line}\n"

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def refresh():
    if not EMAIL or not PASSWORD or EMAIL == "seu_email@exemplo.com":
        print("[ERRO] Preencha LINKEDIN_EMAIL e LINKEDIN_PASSWORD no .env antes de continuar.")
        return False

    print(f"Fazendo login como {EMAIL}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.goto("https://www.linkedin.com/login")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(3)

        # Preencher email — tenta múltiplos seletores
        email_sel = 'input[name="session_key"], #username, input[type="email"], input[autocomplete="username"]'
        page.wait_for_selector(email_sel, timeout=15000)
        page.fill(email_sel, EMAIL)
        time.sleep(0.5)

        # Preencher senha
        pass_sel = 'input[name="session_password"], #password, input[type="password"]'
        page.fill(pass_sel, PASSWORD)
        time.sleep(0.5)

        # Clicar em entrar
        page.click('button[type="submit"], button[data-litms-control-urn="login-submit"]')
        time.sleep(6)

        current_url = page.url
        print(f"URL após login: {current_url}")

        # Verificar se caiu em verificação/captcha
        if "checkpoint" in current_url or "challenge" in current_url:
            print("[AVISO] LinkedIn pediu verificação adicional (captcha/2FA).")
            print("        Faça o login manualmente e copie o li_at do navegador.")
            browser.close()
            return False

        if "feed" not in current_url and "login" in current_url:
            print("[ERRO] Login falhou. Verifique email e senha no .env.")
            browser.close()
            return False

        # Pegar o cookie li_at
        cookies = context.cookies()
        li_at = next((c["value"] for c in cookies if c["name"] == "li_at"), None)

        browser.close()

    if not li_at:
        print("[ERRO] Cookie li_at não encontrado após login.")
        return False

    update_env("LINKEDIN_LI_AT", li_at)
    print(f"[OK] Cookie li_at atualizado no .env com sucesso!")
    print(f"     {li_at[:40]}...")
    return True


if __name__ == "__main__":
    refresh()
