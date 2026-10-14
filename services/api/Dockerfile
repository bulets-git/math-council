FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8080 8000

CMD ["sh", "-c", "alembic upgrade head || echo 'Alembic migration deferred'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
