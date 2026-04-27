import os
import time
import google.generativeai as genai
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")
LLM_API_KEY = os.getenv("LLM_API_KEY")

# Carregar instruções do agente
with open("instructions.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

genai.configure(api_key=LLM_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT)


def gerar_comentario(texto_post: str) -> str | None:
    """Usa o Gemini para gerar um comentário relevante para o post."""
    prompt = f"""Analise o post abaixo e decida se vale a pena comentar.
Se sim, gere um comentário autêntico seguindo suas instruções.
Se não vale comentar, responda exatamente: IGNORAR

Post:
{texto_post[:1000]}

Responda apenas com o comentário ou com IGNORAR."""

    try:
        response = model.generate_content(prompt)
        resultado = response.text.strip()
        if resultado.upper() == "IGNORAR":
            return None
        return resultado
    except Exception as e:
        print(f"  [Gemini] Erro ao gerar comentário: {e}")
        return None


def extrair_posts(page) -> list[dict]:
    """Extrai posts do feed do LinkedIn."""
    posts = []

    # Seletores em ordem de prioridade
    container_selectors = [
        'div[data-urn^="urn:li:activity:"]',
        'div[data-id^="urn:li:activity:"]',
        '.feed-shared-update-v2',
        '.occludable-update',
    ]

    post_elements = []
    for selector in container_selectors:
        elements = page.locator(selector).all()
        if elements:
            print(f"  Seletor funcionando: {selector} ({len(elements)} posts)")
            post_elements = elements
            break

    if not post_elements:
        print("  Nenhum seletor encontrou posts. Verifique o cookie li_at.")
        return posts

    text_selectors = [
        ".update-components-text",
        ".feed-shared-update-v2__description",
        ".feed-shared-inline-show-more-text",
        "[data-test-id='main-feed-activity-card__commentary']",
    ]

    author_selectors = [
        ".update-components-actor__name",
        ".feed-shared-actor__name",
        ".update-components-actor__title",
    ]

    for idx, post in enumerate(post_elements[:10]):
        try:
            autor = "Desconhecido"
            for sel in author_selectors:
                loc = post.locator(sel)
                if loc.count() > 0:
                    texto_autor = loc.first.inner_text().strip().split("\n")[0]
                    if texto_autor:
                        autor = texto_autor
                        break

            texto = ""
            for sel in text_selectors:
                loc = post.locator(sel)
                if loc.count() > 0:
                    texto = loc.first.inner_text().strip()
                    if texto:
                        break

            # Pegar URN para identificar o post
            urn = post.get_attribute("data-urn") or post.get_attribute("data-id") or f"post_{idx}"

            if texto:
                posts.append({"urn": urn, "autor": autor, "texto": texto, "element": post})
                print(f"  Post {idx+1}: {autor[:40]} — {texto[:80]}...")

        except Exception as e:
            print(f"  Erro ao extrair post {idx+1}: {e}")

    return posts


def curtir_post(post: dict):
    """Curte um post clicando no botão de like."""
    try:
        like_btn = post["element"].locator(
            'button[aria-label*="curtir"], button[aria-label*="Like"], '
            'button[data-control-name="like_toggle"]'
        ).first
        if like_btn.count() > 0:
            like_btn.click()
            time.sleep(1)
            print(f"  👍 Curtido: {post['autor'][:40]}")
    except Exception as e:
        print(f"  Erro ao curtir: {e}")


def comentar_post(page, post: dict, comentario: str):
    """Deixa um comentário em um post."""
    try:
        comment_btn = post["element"].locator(
            'button[aria-label*="comentar"], button[aria-label*="Comment"], '
            'button[data-control-name="comment"]'
        ).first
        if comment_btn.count() == 0:
            print(f"  Botão de comentário não encontrado para: {post['autor'][:40]}")
            return

        comment_btn.click()
        time.sleep(2)

        # Campo de texto do comentário
        comment_box = page.locator(
            '.comments-comment-box__form .ql-editor, '
            '.comments-comment-texteditor .ql-editor, '
            '[data-placeholder*="comentário"], [data-placeholder*="comment"]'
        ).first
        comment_box.click()
        comment_box.type(comentario, delay=30)
        time.sleep(1)

        # Enviar
        submit_btn = page.locator(
            'button[data-control-name="submit_comment"], '
            '.comments-comment-box__submit-button'
        ).first
        submit_btn.click()
        time.sleep(2)
        print(f"  💬 Comentado em: {post['autor'][:40]}")
        print(f"     → {comentario[:100]}")

    except Exception as e:
        print(f"  Erro ao comentar: {e}")


def main():
    print("=" * 50)
    print("  OpenClaw LinkedIn Agent")
    print("=" * 50)

    if not LINKEDIN_LI_AT:
        print("[ERRO] LINKEDIN_LI_AT não definido no .env")
        return
    if not LLM_API_KEY:
        print("[ERRO] LLM_API_KEY não definido no .env")
        return

    with sync_playwright() as p:
        print("\n[1/4] Iniciando navegador headless...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        context.add_cookies([{
            "name": "li_at",
            "value": LINKEDIN_LI_AT,
            "domain": ".www.linkedin.com",
            "path": "/",
        }])

        page = context.new_page()

        print("[2/4] Acessando feed do LinkedIn...")
        page.goto("https://www.linkedin.com/feed/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(5)

        # Verificar se está logado
        if "login" in page.url or "authwall" in page.url:
            print("[ERRO] Cookie expirado ou inválido. Renove o li_at no .env")
            browser.close()
            return

        print("[3/4] Carregando posts...")
        for _ in range(3):
            page.keyboard.press("PageDown")
            time.sleep(2)

        posts = extrair_posts(page)
        print(f"\n  Total de posts encontrados: {len(posts)}")

        if not posts:
            print("[AVISO] Nenhum post extraído. Verifique o cookie li_at.")
            browser.close()
            return

        print("\n[4/4] Processando posts com Gemini...")
        curtidos = 0
        comentados = 0

        for post in posts:
            print(f"\n--- Analisando post de: {post['autor'][:50]} ---")
            comentario = gerar_comentario(post["texto"])

            # Sempre curte
            curtir_post(post)
            curtidos += 1

            # Comenta se o Gemini decidiu que vale
            if comentario:
                comentar_post(page, post, comentario)
                comentados += 1
            else:
                print("  ⏭️  Gemini decidiu ignorar este post")

            time.sleep(2)  # Pausa entre interações

        print("\n" + "=" * 50)
        print(f"  Concluído: {curtidos} curtidas | {comentados} comentários")
        print("=" * 50)

        browser.close()


if __name__ == "__main__":
    main()
