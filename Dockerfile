# ---- Stage 1: build the React app ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
ENV CI=false GENERATE_SOURCEMAP=false
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: API + static frontend ----
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 NEXFLOW_DB=/data/nexflow.db
WORKDIR /app

RUN useradd --create-home --uid 10001 nexflow && mkdir -p /data && chown nexflow:nexflow /data

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/build ./frontend/build

USER nexflow
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# One worker on purpose: login rate limiting and run limits are tracked in process memory.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
