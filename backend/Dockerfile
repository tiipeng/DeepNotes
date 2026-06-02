FROM python:3.12-slim

WORKDIR /app

# System libraries required by docling (OpenCV), rapidocr, and faster-whisper
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Default data directory — override via environment / docker-compose volume mount
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:////data/deepnotes.db \
    CHROMA_DIR=/data/chroma \
    TABLES_PATH=/data/tables.duckdb

EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
