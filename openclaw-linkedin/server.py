"""
server.py — Interface web local para o OpenClaw LinkedIn Agent
Credenciais ficam APENAS em memória RAM. Nunca são gravadas em disco.
Rode: python server.py
Acesse: http://localhost:8080
"""
import os
import threading
import time
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI()

# ─────────────────────────────────────────────
# CREDENCIAIS: apenas em memória, nunca em disco
# ─────────────────────────────────────────────
credentials = {
    "email": None,
    "password": None,
    "llm_key": None,
    "li_at": None,   # preenchido automaticamente após login
}

# Estado global do agente
state = {
    "running": False,
    "current_loop": 0,
    "total_loops": 3,
    "interval_minutes": 30,
    "logs": [],
    "stats": {"reactions": 0, "comments": 0, "posts_processed": 0},
    "started_at": None,
    "next_cycle_at": None,
}


def add_log(message: str, level: str = "info"):
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "level": level,
    }
    state["logs"].append(entry)
    if len(state["logs"]) > 200:
        state["logs"] = state["logs"][-200:]
    print(f"[{entry['time']}] {message}")


def renovar_cookie() -> str | None:
    """Faz login no LinkedIn e retorna o li_at. Nunca salva em disco."""
    from playwright.sync_api import sync_playwright

    email = credentials["email"]
    password = credentials["password"]

    if not email or not password:
        add_log("Email/senha não fornecidos. Pulando renovação de cookie.", "warning")
        return credentials.get("li_at")

    add_log(f"Fazendo login como {email}...", "info")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            time.sleep(3)

            email_sel = 'input[name="session_key"], #username, input[type="email"]'
            page.wait_for_selector(email_sel, timeout=15000)
            page.fill(email_sel, email)
            page.fill('input[name="session_password"], #password, input[type="password"]', password)
            page.click('button[type="submit"]')
            time.sleep(6)

            if "checkpoint" in page.url or "challenge" in page.url:
                add_log("LinkedIn pediu verificação adicional (2FA/captcha).", "error")
                browser.close()
                return credentials.get("li_at")

            if "login" in page.url:
                add_log("Login falhou. Verifique email e senha.", "error")
                browser.close()
                return None

            cookies = context.cookies()
            li_at = next((c["value"] for c in cookies if c["name"] == "li_at"), None)
            browser.close()

        if li_at:
            credentials["li_at"] = li_at  # apenas em memória
            add_log("Cookie li_at renovado (apenas em memória).", "success")
            return li_at
        else:
            add_log("Cookie li_at não encontrado após login.", "error")
            return None

    except Exception as e:
        add_log(f"Erro ao renovar cookie: {e}", "error")
        return None


def run_agent():
    """Roda o agente em background. Credenciais usadas apenas da memória."""
    from playwright.sync_api import sync_playwright
    from google import genai
    from google.genai import types

    llm_key = credentials.get("llm_key")
    if not llm_key:
        add_log("ERRO: Gemini API Key não fornecida.", "error")
        state["running"] = False
        return

    instructions_path = os.path.join(os.path.dirname(__file__), "instructions.md")
    with open(instructions_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    client = genai.Client(api_key=llm_key)
    MODEL = "gemini-3.1-flash-lite-preview"

    total = state["total_loops"]
    interval = state["interval_minutes"]

    for loop in range(1, total + 1):
        if not state["running"]:
            add_log("Agente interrompido pelo usuário.", "warning")
            break

        state["current_loop"] = loop
        add_log(f"=== CICLO {loop} de {total} iniciado ===", "info")

        # Renovar cookie (apenas em memória)
        li_at = renovar_cookie()
        if not li_at:
            add_log("Sem cookie válido. Encerrando.", "error")
            break

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                context.add_cookies([{
                    "name": "li_at", "value": li_at,
                    "domain": ".www.linkedin.com", "path": "/",
                }])
                page = context.new_page()

                add_log("Acessando feed do LinkedIn...", "info")
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                time.sleep(10)

                if "login" in page.url or "authwall" in page.url:
                    add_log("Cookie inválido ou expirado.", "error")
                    browser.close()
                    break

                for _ in range(3):
                    page.keyboard.press("PageDown")
                    time.sleep(2)

                from agent import JS_EXTRACT, curtir_post, comentar_post
                dados = page.evaluate(JS_EXTRACT)

                if not dados:
                    add_log("Nenhum post encontrado neste ciclo.", "warning")
                    browser.close()
                else:
                    add_log(f"{len(dados)} posts encontrados.", "info")
                    cycle_reactions = 0
                    cycle_comments = 0

                    for idx, d in enumerate(dados):
                        if not state["running"]:
                            break

                        autor = d.get("autor", "Desconhecido")[:50]
                        texto = d.get("texto", "")
                        add_log(f"Processando: {autor}", "info")

                        try:
                            prompt = f"""Analyze the post below and decide if it's worth commenting on.
If yes, write an authentic comment in ENGLISH following your instructions.
If not worth commenting, reply exactly: IGNORE

Post: {texto[:800]}

Reply only with the comment in English or with IGNORE."""
                            response = client.models.generate_content(
                                model=MODEL,
                                contents=prompt,
                                config=types.GenerateContentConfig(system_instruction=system_prompt),
                            )
                            comentario = response.text.strip()
                            if comentario.upper() == "IGNORE":
                                comentario = None
                        except Exception as e:
                            add_log(f"Gemini erro: {e}", "error")
                            comentario = None

                        curtir_post(page, idx, autor)
                        cycle_reactions += 1
                        state["stats"]["reactions"] += 1
                        add_log(f"  👍 Reagido: {autor}", "success")

                        if comentario:
                            comentar_post(page, idx, autor, comentario)
                            cycle_comments += 1
                            state["stats"]["comments"] += 1
                            add_log(f"  💬 Comentado: {comentario[:80]}...", "success")
                        else:
                            add_log(f"  ⏭️  Ignorado pelo Gemini", "info")

                        state["stats"]["posts_processed"] += 1
                        time.sleep(2)

                    add_log(f"Ciclo {loop} concluído: {cycle_reactions} reações, {cycle_comments} comentários.", "success")
                    browser.close()

        except Exception as e:
            add_log(f"Erro no ciclo {loop}: {e}", "error")

        if loop < total and state["running"]:
            next_time = datetime.fromtimestamp(time.time() + interval * 60)
            state["next_cycle_at"] = next_time.strftime("%H:%M:%S")
            add_log(f"Aguardando {interval} minutos. Próximo ciclo às {state['next_cycle_at']}...", "info")
            for _ in range(interval * 60):
                if not state["running"]:
                    break
                time.sleep(1)

    # Limpar credenciais da memória ao finalizar
    credentials["li_at"] = None
    state["running"] = False
    state["current_loop"] = 0
    state["next_cycle_at"] = None
    add_log("=== Agente finalizado. Credenciais removidas da memória. ===", "info")


@app.get("/", response_class=HTMLResponse)
async def index():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/start")
async def start_agent(background_tasks: BackgroundTasks, data: dict = {}):
    if state["running"]:
        return JSONResponse({"error": "Agente já está rodando."}, status_code=400)

    if not credentials.get("email") and not credentials.get("li_at"):
        return JSONResponse({"error": "Configure suas credenciais antes de iniciar."}, status_code=400)

    if not credentials.get("llm_key"):
        return JSONResponse({"error": "Gemini API Key não configurada."}, status_code=400)

    state["total_loops"] = int(data.get("loops", 3))
    state["interval_minutes"] = int(data.get("interval", 30))
    state["running"] = True
    state["started_at"] = datetime.now().strftime("%H:%M:%S")
    state["logs"] = []
    state["stats"] = {"reactions": 0, "comments": 0, "posts_processed": 0}

    background_tasks.add_task(run_agent)
    add_log(f"Agente iniciado: {state['total_loops']} ciclos de {state['interval_minutes']} minutos.", "success")
    return {"status": "started"}


@app.post("/stop")
async def stop_agent():
    state["running"] = False
    add_log("Solicitação de parada enviada.", "warning")
    return {"status": "stopping"}


@app.post("/set-credentials")
async def set_credentials(data: dict):
    """
    Recebe credenciais e armazena APENAS em memória RAM.
    Nunca grava em disco, banco de dados ou logs.
    """
    if data.get("email"):
        credentials["email"] = data["email"]
    if data.get("password"):
        credentials["password"] = data["password"]
    if data.get("llm_key"):
        credentials["llm_key"] = data["llm_key"]

    # Confirmar sem revelar os valores
    configured = {
        "email": bool(credentials["email"]),
        "password": bool(credentials["password"]),
        "llm_key": bool(credentials["llm_key"]),
    }
    return {"status": "ok", "configured": configured}


@app.post("/clear-credentials")
async def clear_credentials():
    """Apaga todas as credenciais da memória imediatamente."""
    credentials["email"] = None
    credentials["password"] = None
    credentials["llm_key"] = None
    credentials["li_at"] = None
    return {"status": "cleared"}


@app.get("/credentials-status")
async def credentials_status():
    """Retorna apenas se cada credencial está configurada (true/false), nunca o valor."""
    return {
        "email": bool(credentials["email"]),
        "password": bool(credentials["password"]),
        "llm_key": bool(credentials["llm_key"]),
        "li_at": bool(credentials["li_at"]),
    }


@app.get("/status")
async def get_status():
    return {
        "running": state["running"],
        "current_loop": state["current_loop"],
        "total_loops": state["total_loops"],
        "interval_minutes": state["interval_minutes"],
        "started_at": state["started_at"],
        "next_cycle_at": state["next_cycle_at"],
        "stats": state["stats"],
        "logs": state["logs"][-50:],
    }


if __name__ == "__main__":
    print("🚀 OpenClaw LinkedIn Agent — Interface Web")
    print("   Acesse: http://localhost:8080")
    print("   ⚠️  Credenciais ficam APENAS em memória RAM.")
    uvicorn.run(app, host="0.0.0.0", port=8080)
