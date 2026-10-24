# ChillPrint API for Cloud Run. Data is staged into deploy_data/ by scripts/stage_api_data.py;
# the CIMIS key arrives as an environment variable at deploy time, never in the image.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NUMBA_CACHE_DIR=/tmp/numba
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app/engine
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY chillprint ./chillprint
COPY deploy_data ./data
CMD exec uvicorn chillprint.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --log-level warning
