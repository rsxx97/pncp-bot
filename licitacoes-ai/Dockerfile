FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright chromium para scraping ao vivo do ComprasNet
RUN playwright install --with-deps chromium

COPY . .

RUN mkdir -p data/editais data/planilhas data/ccts

EXPOSE 8001

CMD ["python", "start.py"]
