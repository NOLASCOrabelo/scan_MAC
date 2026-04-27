FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Garante que o Playwright usa o Chromium já instalado na imagem
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "agent.py"]
