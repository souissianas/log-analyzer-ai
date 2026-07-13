FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libpq-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary=:all: --no-binary=chroma-hnswlib,fpdf --require-hashes -r requirements.txt

COPY . .

# SonarCloud: "The 'python' image runs with 'root' as the default user."
# Create a dedicated non-root user and hand ownership of /app to it.
# Must happen AFTER `COPY . .` so the copied files are actually owned
# by the new user (chown after copy, not before).
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/false -M appuser && \
    chown -R appuser:appuser /app

USER 1000
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
