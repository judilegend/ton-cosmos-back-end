FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installer dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    shared-mime-info \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries 10 -r requirements.txt

COPY . .

RUN cp -r /app/ephe/. /usr/share/ephe/ && \
    mkdir -p /app/static/reports /app/static/storage && \
    useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app /usr/share/ephe
USER appuser

ENV SE_EPHE_PATH=/usr/share/ephe/

EXPOSE 8000

# Healthcheck : vérifie que l'API répond (30s de délai au démarrage)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Alembic migre le schéma AVANT le démarrage de l'app
# (idempotent : safe sur une base déjà à jour)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
