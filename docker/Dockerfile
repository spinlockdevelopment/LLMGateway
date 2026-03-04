FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy config
COPY config/ config/

# Create data directory for SQLite
RUN mkdir -p data

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/admin/health || exit 1

CMD ["uvicorn", "llm_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
