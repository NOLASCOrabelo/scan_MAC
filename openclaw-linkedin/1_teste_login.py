import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import time

# Carrega as variáveis do arquivo .env
load_dotenv()

LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")

if not LINKEDIN_LI_AT or LINKEDIN_LI_AT == "seu_cookie_gigante_aqui":
    print("ERRO: O cookie 'li_at' não foi encontrado ou ainda é o valor de exemplo no arquivo .env!")
    print("Por favor, preencha o arquivo .env corretamente.")
    exit(1)

def testar_login():
    with sync_playwright() as p:
        print("Iniciando o navegador...")
        # Lança o navegador visível (headless=False) para vermos o que está acontecendo
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        # Adiciona o cookie de sessão do LinkedIn no contexto do navegador
        print("Injetando cookie de autenticação...")
        context.add_cookies([{
            "name": "li_at",
            "value": LINKEDIN_LI_AT,
            "domain": ".www.linkedin.com",
            "path": "/"
        }])

        page = context.new_page()
        
        print("Acessando o feed do LinkedIn...")
        # Acessa diretamente o feed. O cookie li_at deve contornar o login.
        page.goto("https://www.linkedin.com/feed/")
        
        # Espera um pouco para a página carregar
        page.wait_for_load_state("domcontentloaded")
        time.sleep(5) # Espera extra para garantir que a página renderize
        
        # Verifica se conseguimos acessar a página logada procurando algo que só aparece logado
        # Ex: barra de navegação global
        if page.locator("#global-nav").is_visible() or "feed" in page.url:
            print("\nSUCESSO: O agente conseguiu entrar no LinkedIn usando seu cookie!")
            
            # Tira um print da tela para salvar a prova
            caminho_print = "print_login_sucesso.png"
            page.screenshot(path=caminho_print)
            print(f"Um print da tela foi salvo como '{caminho_print}' na pasta do projeto.")
        else:
            print("\nFALHA: Não parece que estamos logados. O cookie li_at pode estar vencido ou incorreto.")
            caminho_print = "print_login_falha.png"
            page.screenshot(path=caminho_print)
            print(f"Um print da tela de falha foi salvo como '{caminho_print}'.")
            
        print("Fechando navegador em 3 segundos...")
        time.sleep(3)
        browser.close()

if __name__ == "__main__":
    print("=== Iniciando Parte 1: Teste de Login ===")
    testar_login()
