import telebot
import subprocess
import time

# ==========================================
# CONFIGURAÇÕES
# ==========================================
TOKEN = "8619219181:AAF5laHxpjIJ-w3SBvZeSWsjvqCyBSjR_2c"
WHITELIST = "/opt/scandemac_bot/whitelist.txt"

# Inicia a conexão com o bot
bot = telebot.TeleBot(TOKEN)

print("🛡️ Bot Ouvinte de Segurança iniciado. Aguardando comandos...")

# ==========================================
# LÓGICA DOS BOTÕES (CALLBACKS)
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def processar_botoes(call):
    # O call.data traz a informação do botão que criamos no scan.sh (Ex: "add_00:11..._192.168...")
    dados = call.data.split('_')
    acao = dados[0]
    mac_alvo = dados[1]
    ip_alvo = dados[2]

    # ====== AÇÃO 1: RECONHEÇO (Adicionar à Whitelist) ======
    if acao == "add":
        # Escreve o MAC no final do arquivo de whitelist
        with open(WHITELIST, "a") as arquivo:
            arquivo.write(mac_alvo + "\n")
        
        # Tira a barrinha de carregamento do botão no Telegram
        bot.answer_callback_query(call.id, "Sucesso! MAC adicionado à lista.")
        
        # Edita a mensagem para o botão sumir e ficar o registro da sua ação
        mensagem_sucesso = f"✅ *Resolvido:* O MAC `{mac_alvo}` (IP: {ip_alvo}) foi autorizado e adicionado à Whitelist!"
        bot.edit_message_text(chat_id=call.message.chat.id, 
                              message_id=call.message.message_id, 
                              text=mensagem_sucesso, 
                              parse_mode="Markdown")

    # ====== AÇÃO 2: NÃO RECONHEÇO (Investigar via Nmap) ======
    elif acao == "scan":
        bot.answer_callback_query(call.id, "Iniciando varredura profunda...")
        
        # Avisa no chat que o scan começou (pois o nmap -A demora um pouco)
        msg_espera = bot.send_message(call.message.chat.id, 
                                      f"⏳ *Investigando* o IP {ip_alvo} (MAC: {mac_alvo}).\n\nIsso levará alguns segundos, analisando Sistema Operacional e Portas...", 
                                      parse_mode="Markdown")
        
        # Executa o comando Nmap direto no terminal do Linux usando o subprocess
        comando_nmap = f"nmap -A -T4 -Pn {ip_alvo} | grep -E '^[0-9]|OS details|Service Info|MAC Address'"
        
        try:
            # Roda o comando e captura a saída
            processo = subprocess.run(comando_nmap, shell=True, capture_output=True, text=True)
            resultado = processo.stdout
            
            # Se o Nmap não achar nada, define uma mensagem padrão
            if not resultado.strip():
                resultado = "Nenhuma porta aberta ou serviço identificado com clareza."
                
        except Exception as e:
            resultado = f"Erro ao executar o Nmap: {e}"

        # Formata o relatório final e envia de volta
        relatorio_final = f"🚨 *RESULTADO DA INVESTIGAÇÃO:* 🚨\n*Alvo:* {ip_alvo}\n\n```text\n{resultado}\n```"
        bot.send_message(call.message.chat.id, relatorio_final, parse_mode="Markdown")

# Mantém o script rodando 24/7 de forma estável
bot.infinity_polling(timeout=10, long_polling_timeout=5)
