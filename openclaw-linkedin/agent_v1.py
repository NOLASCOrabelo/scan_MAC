import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
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
        
        // Pular posts que não são originais (ex: "X likes this", "Y commented on this", "Suggested")
        const reactionRegex = /likes this|commented on this|reposted this|finds this funny|gostou disso|comentou|republicou|suggested|promoted|patrocinado|achou isto engraçado|apoia isto|supports this/i;
        if (lines[0] && lines[0].match(reactionRegex)) continue;
        if (lines[1] && lines[1].match(reactionRegex)) continue;

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
    """Reage a um post usando JS para contornar o Shadow DOM do LinkedIn."""
    try:
        result = page.evaluate(f"""
        () => {{
            function queryAllShadow(root, selector) {{
                const found = [];
                try {{ found.push(...root.querySelectorAll(selector)); }} catch(e) {{}}
                for (const el of root.querySelectorAll('*')) {{
                    if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
                }}
                return found;
            }}
            const mainFeed = document.querySelector('[data-testid="mainFeed"]');
            const searchRoot = mainFeed || document;
            let containers = Array.from(searchRoot.querySelectorAll('[role="listitem"]'));
            if (!containers.length) containers = Array.from(searchRoot.querySelectorAll('[data-display-contents="true"]'));
            if (!containers.length && mainFeed) containers = Array.from(mainFeed.children);
            if (!containers.length) containers = queryAllShadow(document, '[role="listitem"]');
            
            const valid = containers.filter(c => (c.innerText||'').trim().length > 30);
            const container = valid[{post_index}];
            if (!container) return {{ error: 'container not found' }};
            
            const buttons = queryAllShadow(container, 'button');
            const reactionKeywords = ['like', 'curtir', 'gostei', 'celebrate', 'support', 'love', 'insightful', 'funny', 'reaction button state'];
            
            for (const b of buttons) {{
                const label = ((b.getAttribute('aria-label') || '') + ' ' + (b.innerText || '')).toLowerCase();
                for (const kw of reactionKeywords) {{
                    if (label.includes(kw) && !label.includes('desfazer') && !label.includes('undo')) {{
                        b.click();
                        return {{ success: true, keyword: kw }};
                    }}
                }}
            }}
            return {{ error: 'no reaction button found' }};
        }}
        """)
        
        if result and result.get("success"):
            print(f"  👍 Reagido ({result.get('keyword')}): {autor[:40]}")
        else:
            print(f"  ⚠️  Nenhum botão de reação encontrado para: {autor[:40]}")
            
    except Exception as e:
        print(f"  Erro ao reagir: {e}")


def comentar_post(page, post_index: int, autor: str, comentario: str):
    """Comenta em um post usando JS para contornar o Shadow DOM do LinkedIn."""
    try:
        result = page.evaluate(f"""
        () => {{
            function queryAllShadow(root, selector) {{
                const found = [];
                try {{ found.push(...root.querySelectorAll(selector)); }} catch(e) {{}}
                for (const el of root.querySelectorAll('*')) {{
                    if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
                }}
                return found;
            }}
            const mainFeed = document.querySelector('[data-testid="mainFeed"]');
            const searchRoot = mainFeed || document;
            let containers = Array.from(searchRoot.querySelectorAll('[role="listitem"]'));
            if (!containers.length) containers = Array.from(searchRoot.querySelectorAll('[data-display-contents="true"]'));
            if (!containers.length && mainFeed) containers = Array.from(mainFeed.children);
            if (!containers.length) containers = queryAllShadow(document, '[role="listitem"]');
            
            const valid = containers.filter(c => (c.innerText||'').trim().length > 30);
            const container = valid[{post_index}];
            if (!container) return {{ error: 'container not found' }};
            
            const buttons = queryAllShadow(container, 'button');
            for (const b of buttons) {{
                const label = (b.getAttribute('aria-label') || b.innerText || '').toLowerCase();
                if (label.includes('comment') || label.includes('comentar') || label.includes('comentário')) {{
                    b.click();
                    return {{ success: true }};
                }}
            }}
            return {{ error: 'no comment button found' }};
        }}
        """)
        
        if not result or not result.get("success"):
            print(f"  ⚠️  Botão de comentário não encontrado para: {autor[:40]}")
            return
            
        time.sleep(3)

        # Encontrar campo de texto e focar
        fill_result = page.evaluate("""
        () => {
            function queryAllShadow(root, selector) {
                const found = [];
                try { found.push(...root.querySelectorAll(selector)); } catch(e) {}
                for (const el of root.querySelectorAll('*')) {
                    if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
                }
                return found;
            }
            const boxes = queryAllShadow(document, '[contenteditable="true"][role="textbox"]');
            if (boxes.length > 0) {
                const box = boxes[boxes.length - 1]; // Pegar a última (a do post atual que foi aberta)
                box.focus();
                return { success: true };
            }
            return { error: 'box not found' };
        }
        """)

        if fill_result and fill_result.get("success"):
            time.sleep(1)
            # Digitar simulando teclado tecla a tecla (fundamental para o LinkedIn habilitar o botão)
            page.keyboard.type(comentario, delay=20)
            time.sleep(2)
            
            # Clicar no botão de enviar (Post/Publicar) usando JS
            submit_result = page.evaluate("""
            () => {
                function queryAllShadow(root, selector) {
                    const found = [];
                    try { found.push(...root.querySelectorAll(selector)); } catch(e) {}
                    for (const el of root.querySelectorAll('*')) {
                        if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
                    }
                    return found;
                }
                
                const boxes = queryAllShadow(document, '[contenteditable="true"][role="textbox"]');
                if (boxes.length === 0) return { error: 'box lost' };
                const box = boxes[boxes.length - 1]; // Caixa ativa
                
                let container = box;
                while (container.parentElement) {
                    container = container.parentElement;
                    const btns = queryAllShadow(container, 'button');
                    
                    // Verificar se este container inclui os botões de ação do comentário (Emoji, Foto)
                    const isCommentBoxContainer = btns.some(b => {
                        const a = (b.getAttribute('aria-label') || '').toLowerCase();
                        return a.includes('emoji') || a.includes('photo') || a.includes('foto') || a.includes('image');
                    });
                    
                    if (isCommentBoxContainer) {
                        for (const b of btns) {
                            const label = (b.innerText || '').trim().toLowerCase();
                            if ((label === 'post' || label === 'publicar' || label === 'comment' || label === 'comentar') && !b.disabled) {
                                b.click();
                                return { success: true, btnText: label };
                            }
                        }
                    }
                }
                
                return { error: 'submit button not found near box' };
            }
            """)
            
            time.sleep(2)
            if submit_result and submit_result.get("success"):
                print(f"  💬 Comentado em: {autor[:40]}")
                print(f"     → {comentario[:100]}")
            else:
                # Fallback tentar control enter se não achou o botão
                page.keyboard.press("Control+Enter")
                time.sleep(2)
                print(f"  💬 Comentado em: {autor[:40]} (via Control+Enter)")
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

    print("\n[Limpeza] Aguardando 1 minuto para apagar as screenshots geradas...")
    time.sleep(60)
    try:
        import glob
        apagadas = 0
        for f in glob.glob("screenshot_*.png"):
            os.remove(f)
            apagadas += 1
        print(f"  {apagadas} screenshots apagadas com sucesso.")
    except Exception as e:
        print(f"  Erro ao apagar screenshots: {e}")


if __name__ == "__main__":
    main()
