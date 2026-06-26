FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies for psycopg2-binary wheels (kept for safety) and
# any small build deps that might be needed by transformers/torch wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only torch FIRST so we don't pull the CUDA build (~2 GB).
# Pinning to a known-good recent version.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.1

# Install remaining Python deps (transformers will use the cpu torch above).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the HF model weights into the image at /opt/hf-cache so the runtime
# container does not need network access to huggingface.co.
ENV HF_HOME=/opt/hf-cache
RUN mkdir -p /opt/hf-cache && \
    python -c "\
from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
tok = AutoTokenizer.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english'); \
mdl = AutoModelForSequenceClassification.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english'); \
print('HF model baked into', '/opt/hf-cache')"

# Runtime flag: fail loudly if weights aren't present locally.
ENV TRANSFORMERS_OFFLINE=1 \
    MODEL_NAME=distilbert-base-uncased-finetuned-sst-2-english

# Copy application code last to maximize Docker layer caching.
COPY app/ /app/app/

EXPOSE 8000

# Container-level healthcheck so docker compose / orchestrators can
# detect a successful model load and HTTP response.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]