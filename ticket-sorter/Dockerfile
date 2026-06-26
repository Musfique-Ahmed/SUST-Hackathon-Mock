FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only what we need: FastAPI, Uvicorn, Pydantic. No torch, no
# transformers, no DB drivers. The resulting image is ~150 MB.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application last to maximise Docker layer caching.
COPY app/ /app/app/

EXPOSE 8000

# Container-level liveness probe: hit /health and require "ok".
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).read().decode().strip() == '{\"status\":\"ok\"}' else 1)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]