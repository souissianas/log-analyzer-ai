FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first (Docker cache)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --requirement requirements.txt

# Copy only application files
COPY main.py .
COPY alembic.ini .
COPY worker.py .
COPY get_logs.py .
COPY setup_files.py .
COPY pytest.ini .

COPY alembic ./alembic
COPY core ./core
COPY routers ./routers
COPY schemas ./schemas
COPY services ./services

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
