# OpenClaw LinkedIn Engagement Agent

Este projeto é um agente automatizado especializado em engajamento no LinkedIn. Ele utiliza Python e Playwright para navegar na rede, ler publicações e realizar interações estratégicas e autênticas.

## Objetivos do Agente

- **Curtir Publicações**: Interagir consistentemente com posts de conexões relevantes e influenciadores.
- **Comentar com Propósito**: Deixar comentários bem elaborados que demonstrem pensamento crítico e agreguem valor à discussão, fugindo de clichês gerados por IA.
- **Construção de Autoridade**: Manter uma presença ativa e genuína que posicione o perfil de forma autêntica em sua área de atuação.

## Funcionalidades

- **Interação Automatizada via Playwright**: Simulação de um navegador real para interagir de forma orgânica.
- **Simulação de Comportamento Humano (Random Timer)**: Uso de atrasos aleatórios configuráveis para rolagem, digitação caractere por caractere e esperas no feed, reduzindo detecção de automação.
- **Geração de Comentários Multilíngue**: Suporte à geração de comentários autênticos em Português (pt-BR) e Inglês (en-US) com distribuição configurável.
- **Interface Web de Monitoramento (FastAPI)**: Dashboard interativo para iniciar/parar o agente, gerenciar credenciais (incluindo o cookie `li_at`), definir intervalos de ciclo e visualizar logs em tempo real.
- **Execução via Docker**: O ambiente é facilmente provisionado utilizando contêineres Docker, simplificando a instalação e gestão de dependências do Playwright.

## Estrutura do Projeto

- `agent.py`: Script principal de execução do agente.
- `server.py`: Servidor web FastAPI para gerenciar e monitorar o agente.
- `random_timer.py`: Classe auxiliar para gerar intervalos e simular comportamento humano.
- `templates/index.html`: Interface visual do painel do agente.
- `Dockerfile` e `docker-compose.yml`: Arquivos para build e execução do ambiente isolado.
- `instructions.md`: Arquivo com as instruções (prompt) que guiam o comportamento, tom e restrições do agente de IA.
- `requirements.txt`: Dependências do projeto (Playwright, FastAPI, GenAI, etc.).

## Como Executar

### Pré-requisitos
- [Docker](https://www.docker.com/) e [Docker Compose](https://docs.docker.com/compose/) instalados.

### Passos

1. Configure as credenciais e variáveis de ambiente necessárias (verifique o arquivo `.env`).
2. Faça o build e inicie o contêiner:
   ```bash
   docker-compose up -d --build
   ```
3. O painel web estará acessível na porta configurada (ex: `http://localhost:8000`), onde você poderá acompanhar o status, iniciar o agente e ver os logs em tempo real.
4. Você também pode acompanhar os logs do terminal com:
   ```bash
   docker-compose logs -f
   ```

## Boas Práticas e Restrições

Conforme definido em suas instruções centrais, o agente está proibido de se engajar com conteúdos ofensivos, políticos ou fora do domínio profissional estabelecido. Ocasionalmente, se o contexto for incerto, a instrução principal do agente o orienta a pular a postagem, mantendo a autenticidade e a segurança da conta.

