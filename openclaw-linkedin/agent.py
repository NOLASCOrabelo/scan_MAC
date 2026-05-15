import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")
LLM_API_KEY = os.getenv("LLM_API_KEY")

# Carregar instruções do agente
with open("instructions.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

client = genai.Client(api_key=LLM_API_KEY)
MODEL = "gemini-3.1-flash-lite-preview"


def gerar_comentario(texto_post: str) -> str | None:
    """Usa o Gemini para gerar um comentário relevante para o post."""
    prompt = f"""Analyze the post below and decide if it's worth commenting on.
If yes, write an authentic comment in ENGLISH following your instructions.
If not worth commenting, reply exactly: IGNORE

Post:
{texto_post[:1000]}

Reply only with the comment in English or with IGNORE."""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        resultado = response.text.strip()
        if resultado.upper() == "IGNORE":
            return None
        return resultado
    except Exception as e:
        print(f"  [Gemini] Erro ao gerar comentário: {e}")
        return None


JS_EXTRACT = """
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

    const results = [];
    for (const c of containers.slice(0, 15)) {
        const fullText = (c.innerText || c.textContent || '').trim();
        if (fullText.length < 30) continue;

        // Extrair autor: primeira linha significativa
        const lines = fullText.split('\\n').map(l => l.trim()).filter(l => l.length > 2);
        let autor = 'Desconhecido';
        // Pular linhas genéricas de reação ("X finds this funny", "Promoted", etc)
        for (const line of lines) {
            if (line.length > 3 && line.length < 80 &&
                !line.match(/^(Feed post|Promoted|Follow|Like|Comment|Share|Send|\\d+)/i)) {
                autor = line;
                break;
            }
        }

        // Extrair texto do post: linha mais longa com conteúdo real
        let texto = '';
        for (const line of lines) {
            if (line.length > 80) { texto = line; break; }
        }
        if (!texto) {
            const longLines = lines.filter(l => l.length > 30);
            texto = longLines.slice(0, 3).join(' ');
        }

        if (texto && texto.length > 20) {
            results.push({ autor: autor.slice(0, 100), texto: texto.slice(0, 800) });
        }
        if (results.length >= 10) break;
    }
    return results;
}
"""


def extrair_posts(page) -> list[dict]:
    """Extrai posts do feed usando JS para acessar Shadow DOM do novo LinkedIn."""
    posts = []

    print("  Aguardando feed carregar no Shadow DOM...")
    time.sleep(5)

    dados = page.evaluate(JS_EXTRACT)

    if not dados:
        print("  Nenhum post extraído. Salvando HTML para debug...")
        with open("feed_live_debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        return posts

    for idx, d in enumerate(dados):
        posts.append({
            "urn": f"post_{idx}",
            "autor": d.get("autor", "Desconhecido"),
            "texto": d.get("texto", ""),
            "element": None,
        })
        print(f"  Post {idx+1}: {d['autor'][:40]} — {d['texto'][:80]}...")

    return posts


JS_INTERACT = """
(postIndex) => {
    const mainFeed = document.querySelector('[data-testid="mainFeed"]');
    const searchRoot = mainFeed || document;
    let containers = Array.from(searchRoot.querySelectorAll('[role="listitem"]'));
    if (!containers.length) containers = Array.from(searchRoot.querySelectorAll('[data-display-contents="true"]'));
    if (!containers.length && mainFeed) containers = Array.from(mainFeed.children);

    const validContainers = containers.filter(c => (c.innerText || '').trim().length > 30);
    const container = validContainers[postIndex];
    if (!container) return { error: 'container not found' };

    const buttons = Array.from(container.querySelectorAll('button'));

    // Qualquer botão de reação (like, celebrate, support, etc.)
    const reactionKeywords = ['like','curtir','gostei','celebrate','celebrar','support','apoiar','love','insightful','funny','interessante'];
    const reactionBtn = buttons.find(b => {
        const label = (b.getAttribute('aria-label') || b.innerText || '').toLowerCase();
        return reactionKeywords.some(k => label.includes(k));
    });

    // Fallback: primeiro botão que não seja "comment", "share", "send"
    const skipKeywords = ['comment','comentar','share','compartilhar','send','enviar','follow','seguir'];
    const fallbackBtn = buttons.find(b => {
        const label = (b.getAttribute('aria-label') || b.innerText || '').toLowerCase();
        return !skipKeywords.some(k => label.includes(k)) && label.length > 0;
    });

    const commentBtn = buttons.find(b => {
        const label = (b.getAttribute('aria-label') || b.innerText || '').toLowerCase();
        return label.includes('comment') || label.includes('comentar') || label.includes('comentário');
    });

    return {
        reactionFound: !!(reactionBtn || fallbackBtn),
        reactionLabel: reactionBtn ? (reactionBtn.getAttribute('aria-label') || reactionBtn.innerText) 
                      : fallbackBtn ? (fallbackBtn.getAttribute('aria-label') || fallbackBtn.innerText) : null,
        commentFound: !!commentBtn,
        commentLabel: commentBtn ? (commentBtn.getAttribute('aria-label') || commentBtn.innerText) : null,
        totalButtons: buttons.length,
    };
}
"""


def curtir_post(page, post_index: int, autor: str):
    """Reage a um post usando Playwright locator (clique real, não JS)."""
    try:
        # Buscar o container do post via JS
        container_info = page.evaluate(f"""
        () => {{
            const mainFeed = document.querySelector('[data-testid="mainFeed"]');
            const searchRoot = mainFeed || document;
            let containers = Array.from(searchRoot.querySelectorAll('[role="listitem"]'));
            if (!containers.length) containers = Array.from(searchRoot.querySelectorAll('[data-display-contents="true"]'));
            if (!containers.length && mainFeed) containers = Array.from(mainFeed.children);
            const valid = containers.filter(c => (c.innerText||'').trim().length > 30);
            const container = valid[{post_index}];
            if (!container) return {{ error: 'container not found' }};
            
            // Marcar o container com um ID único para o Playwright encontrar
            container.setAttribute('data-kiro-post-index', '{post_index}');
            return {{ success: true }};
        }}
        """)
        
        if container_info.get("error"):
            print(f"  ⚠️  {container_info['error']}")
            return

        # Usar Playwright locator para clicar de verdade
        container = page.locator(f'[data-kiro-post-index="{post_index}"]')
        
        # Tentar encontrar botão de reação por aria-label
        reaction_keywords = ['like', 'curtir', 'gostei', 'celebrate', 'support', 'love', 'insightful', 'funny']
        clicked = False
        
        for keyword in reaction_keywords:
            try:
                btn = container.locator(f'button[aria-label*="{keyword}" i]').first
                if btn.count() > 0:
                    btn.click(timeout=3000)
                    clicked = True
                    print(f"  👍 Reagido ({keyword}): {autor[:40]}")
                    break
            except Exception:
                continue
        
        if not clicked:
            print(f"  ⚠️  Nenhum botão de reação encontrado para: {autor[:40]}")
            
    except Exception as e:
        print(f"  Erro ao reagir: {e}")


def comentar_post(page, post_index: int, autor: str, comentario: str):
    """Comenta em um post usando Playwright locator (clique real)."""
    try:
        # Marcar container
        page.evaluate(f"""
        () => {{
            const mainFeed = document.querySelector('[data-testid="mainFeed"]');
            const searchRoot = mainFeed || document;
            let containers = Array.from(searchRoot.querySelectorAll('[role="listitem"]'));
            if (!containers.length) containers = Array.from(searchRoot.querySelectorAll('[data-display-contents="true"]'));
            if (!containers.length && mainFeed) containers = Array.from(mainFeed.children);
            const valid = containers.filter(c => (c.innerText||'').trim().length > 30);
            const container = valid[{post_index}];
            if (container) container.setAttribute('data-kiro-comment-index', '{post_index}');
        }}
        """)
        
        container = page.locator(f'[data-kiro-comment-index="{post_index}"]')
        
        # Clicar no botão de comentário
        comment_btn = container.locator('button[aria-label*="comment" i], button[aria-label*="comentar" i]').first
        if comment_btn.count() == 0:
            print(f"  ⚠️  Botão de comentário não encontrado para: {autor[:40]}")
            return
            
        comment_btn.click(timeout=5000)
        time.sleep(3)

        # Digitar no campo de comentário
        comment_box = page.locator('[contenteditable="true"][role="textbox"]').last
        if comment_box.count() > 0:
            comment_box.click()
            comment_box.fill(comentario)
            time.sleep(1)
            comment_box.press("Control+Enter")
            time.sleep(2)
            print(f"  💬 Comentado em: {autor[:40]}")
            print(f"     → {comentario[:100]}")
        else:
            print(f"  ⚠️  Campo de comentário não encontrado")

    except Exception as e:
        print(f"  Erro ao comentar: {e}")


def main():
    print("=" * 50)
    print("  OpenClaw LinkedIn Agent")
    print("=" * 50)

    if not LLM_API_KEY:
        print("[ERRO] LLM_API_KEY não definido no .env")
        return

    # Tentar renovar cookie automaticamente se credenciais estiverem configuradas
    email = os.getenv("LINKEDIN_EMAIL", "")
    if email and email != "seu_email@exemplo.com":
        print("\n[Cookie] Renovando li_at automaticamente...")
        try:
            from refresh_cookie import refresh
            refresh()
            load_dotenv(override=True)
        except Exception as e:
            print(f"[Cookie] Não foi possível renovar automaticamente: {e}")

    li_at = os.getenv("LINKEDIN_LI_AT")
    if not li_at:
        print("[ERRO] LINKEDIN_LI_AT não definido no .env")
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
            "value": li_at,
            "domain": ".www.linkedin.com",
            "path": "/",
        }])

        page = context.new_page()

        print("[2/4] Acessando feed do LinkedIn...")
        page.goto("https://www.linkedin.com/feed/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(10)

        # Verificar se está logado
        if "login" in page.url or "authwall" in page.url:
            print("[ERRO] Cookie expirado ou inválido. Renove o li_at no .env")
            browser.close()
            return

        print("[3/4] Carregando posts...")
        for _ in range(3):
            page.keyboard.press("PageDown")
            time.sleep(2)

        # Screenshot do feed para confirmar o que está sendo visto
        try:
            page.screenshot(path="screenshot_feed.png", full_page=False, timeout=10000)
            print("  📸 Screenshot salvo: screenshot_feed.png")
        except Exception as e:
            print(f"  ⚠️  Screenshot falhou: {e}")

        posts = extrair_posts(page)
        print(f"\n  Total de posts encontrados: {len(posts)}")

        if not posts:
            print("[AVISO] Nenhum post extraído. Verifique o cookie li_at.")
            browser.close()
            return

        print("\n[4/4] Processando posts com Gemini...")
        curtidos = 0
        comentados = 0

        for idx, post in enumerate(posts):
            print(f"\n--- Analisando post de: {post['autor'][:50]} ---")
            comentario = gerar_comentario(post["texto"])

            # Sempre reage
            curtir_post(page, idx, post["autor"])
            curtidos += 1

            # Screenshot após reagir para confirmar
            try:
                page.screenshot(path=f"screenshot_post_{idx}.png", full_page=False, timeout=10000)
            except Exception:
                pass

            # Comenta se o Gemini decidiu que vale
            if comentario:
                comentar_post(page, idx, post["autor"], comentario)
                try:
                    page.screenshot(path=f"screenshot_comment_{idx}.png", full_page=False, timeout=10000)
                except Exception:
                    pass
                comentados += 1
            else:
                print("  ⏭️  Gemini decidiu ignorar este post")

            time.sleep(2)

        print("\n" + "=" * 50)
        print(f"  Concluído: {curtidos} curtidas | {comentados} comentários")
        print("=" * 50)

        browser.close()


if __name__ == "__main__":
    main()
