import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")

def ler_posts():
    with sync_playwright() as p:
        print("Iniciando o navegador...")
        browser = p.chromium.launch(headless=False)
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
        print("Acessando o feed do LinkedIn...")
        page.goto("https://www.linkedin.com/feed/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(5)
        
        print("Rolando a página para carregar as publicações...")
        # Rolar a página algumas vezes
        for _ in range(3):
            page.keyboard.press("PageDown")
            time.sleep(2)

        print("\n=== EXTRAINDO POSTS ===")
        # Vamos buscar os containers das publicações usando o data-id que é mais estável
        post_elements = page.locator('div[data-urn^="urn:li:activity:"], div[data-id^="urn:li:activity:"]').all()
        
        posts_extraidos = []
        
        for idx, post in enumerate(post_elements[:5]): # Pegar os primeiros 5
            try:
                # Extrair autor (primeiro span com nome)
                autor = "Desconhecido"
                for selector in ['.update-components-actor__name', '.feed-shared-actor__name', 'span[dir="ltr"]']:
                    locator = post.locator(selector)
                    if locator.count() > 0:
                        autor = locator.first.inner_text().strip().split('\n')[0]
                        if autor: break
                        
                # Extrair texto
                texto = ""
                for selector in ['.update-components-text', '.feed-shared-update-v2__description', '.feed-shared-inline-show-more-text']:
                    locator = post.locator(selector)
                    if locator.count() > 0:
                        texto = locator.first.inner_text().strip()
                        if texto: break
                    
                if texto: # Só salva se tiver texto
                    posts_extraidos.append({
                        "autor": autor,
                        "texto": texto
                    })
                    print(f"--- POST {idx+1} ---")
                    print(f"Autor: {autor}")
                    print(f"Texto: {texto[:150]}...\n")
            except Exception as e:
                print(f"Erro ao ler um post: {e}")
                
        print(f"Total de posts lidos com sucesso: {len(posts_extraidos)}")
        
        time.sleep(2)
        browser.close()
        return posts_extraidos

if __name__ == "__main__":
    print("=== Iniciando Parte 2: Extração de Posts ===")
    ler_posts()
