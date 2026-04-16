#!/bin/bash

# ==========================================
# CONFIGURAÇÕES GERAIS
# ==========================================
REDE="192.168.15.0/24"
WHITELIST="/opt/scandemac_bot/whitelist.txt"
TOKEN="8619219181:AAF5laHxpjIJ-w3SBvZeSWsjvqCyBSjR_2c"
CHAT_ID="6317626166"

# ==========================================
# 1. VARREDURA DA REDE
# ==========================================
# O Nmap roda silenciosamente e o comando awk extrai o IP e o MAC lado a lado
nmap -sn $REDE | awk '/Nmap scan report for/{ip=$NF; gsub(/[()]/,"",ip)} /MAC Address:/{print ip, $3}' > /tmp/hosts_ativos.txt

# ==========================================
# 2. ANÁLISE E PERFILAMENTO
# ==========================================
while read -r IP MAC; do
    
    # Ignora linhas vazias (segurança do script)
    if [ -z "$MAC" ]; then continue; fi

    # Verifica se o MAC NÃO está na whitelist (ignorando maiúsculas/minúsculas)
    if ! grep -qi "$MAC" "$WHITELIST"; then
        
        echo "Intruso detectado: IP $IP | MAC $MAC. Iniciando perfilamento..."
        
        # Faz o Perfilamento (Deep Scan)
        # Usamos -F (Fast) para escanear só as 100 portas principais e -sV para ver os serviços
        # O grep filtra a saída para a mensagem do Telegram não ficar gigantesca
        PERFIL=$(nmap -F -sV -T4 -Pn "$IP" | grep -E "^[0-9]|Service Info|MAC Address")
        
        # ==========================================
        # 3. ALERTA NO TELEGRAM
        # ==========================================
        # Envia a mensagem usando formatação Markdown
        curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
            -d chat_id="$CHAT_ID" \
            -d parse_mode="Markdown" \
            --data-urlencode "text=🚨 *ALERTA DE SEGURANÇA - ESXi* 🚨

*Novo dispositivo detectado na rede!*
*IP:* $IP
*MAC:* $MAC

*Perfilamento (Portas e Serviços):*
\`\`\`text
$PERFIL
\`\`\`" > /dev/null
            
    fi

done < /tmp/hosts_ativos.txt

# Limpa o arquivo temporário
rm -f /tmp/hosts_ativos.txt
