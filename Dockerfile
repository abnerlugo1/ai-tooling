# Dockerfile for AI Tooling & Orchestration Platform
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY Documents/ ./Documents/
COPY ingestion/ ./ingestion/
COPY llm_harness/ ./llm_harness/
COPY orchestration/ ./orchestration/
COPY capstones/ ./capstones/
COPY dashboard_db.py .

# Pre-populate SQLite database and Vector Store index at build time
RUN python dashboard_db.py sync --force && \
    python -m ingestion.cli ingest "Documents/dashboard .xlsx" --db .vector_store.db

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/stats || exit 1

CMD ["python", "-m", "llm_harness.server"]
