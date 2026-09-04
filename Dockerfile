FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY carrier_kb ./carrier_kb
COPY docs ./docs
COPY config/sources.production.yaml ./config/sources.production.yaml

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "carrier_kb.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
