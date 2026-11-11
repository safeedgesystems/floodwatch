# ---- Stage 1: build the React frontend --------------------------------
FROM node:22-alpine AS web
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build            # outputs to /src/backend/static

# ---- Stage 2: Python runtime -----------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FLOODWATCH_DB=/data/floodwatch.db
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /src/backend/static ./static
RUN useradd -r -u 10001 floodwatch && mkdir /data && chown floodwatch /data
USER floodwatch
EXPOSE 8000
HEALTHCHECK CMD python -c "import os,urllib.request;urllib.request.urlopen('http://localhost:%s/api/health' % os.getenv('PORT','8000'))"
# Render / Railway / Fly inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
