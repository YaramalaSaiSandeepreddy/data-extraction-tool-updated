FROM python:3.11-slim

# System dependencies needed by pytesseract (OCR) and pdf2image (PDF->image rasterization)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render (and most hosts) inject $PORT at runtime; default to 5002 for local `docker run`
ENV PORT=5002
EXPOSE 5002

CMD gunicorn -w 2 -b 0.0.0.0:${PORT} --timeout 120 src.main:app
