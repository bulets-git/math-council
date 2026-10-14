FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

COPY . .

# Convert Windows line endings → Unix, then make executable
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

EXPOSE 8080

# Railway injects $PORT at runtime. start.sh uses ${PORT:-8080}.
CMD ["./start.sh"]
