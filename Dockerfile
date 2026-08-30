# Single image, two entrypoints: the compose file runs it twice, once as the
# API and once as the UI. One image means one dependency set to keep in sync.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies first: this layer is cached until requirements.txt changes,
# so a code edit does not reinstall the world.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY ui/ ./ui/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Warm the embedding model into the image so the first request is not a
# 130 MB download. Failure is non-fatal: the model downloads at runtime instead.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')" || true

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000 8501

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
