FROM python:3.11-slim

# uv: fast Python package manager (https://docs.astral.sh/uv/)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    HF_HOME=/opt/hf-cache \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1) Dependencies only (cached layer: only rebuilt when pyproject.toml / uv.lock change).
#    CPU-only torch comes from the PyTorch index configured in pyproject.toml.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then uv sync --locked --no-dev --no-install-project; \
    else uv sync --no-dev --no-install-project; fi

# 2) Download the embedding model at build time so the container starts offline.
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-small
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# 3) Application code
COPY . .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
