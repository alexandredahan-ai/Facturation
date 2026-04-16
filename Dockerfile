# Syntax=docker/dockerfile:1.4
FROM python:3.11-slim

# Environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Dépendances système de base
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Le code source
COPY . ${APP_HOME}

# Utilisateur non-root
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser
RUN chown -R appuser:appgroup ${APP_HOME}
USER appuser

# Par défaut, on peut démarrer un serveur web (ex: Flask/FastAPI pour les triggers Cloud Scheduler)
# Vu qu'il s'agit de Cloud Run Jobs ou un service, on laisse l'utilisateur préciser 
# via l'entrypoint ou on lance via uvicorn/gunicorn ou script python raw.
# L'entrypoint va gérer l'aiguillage.
CMD ["python", "-m", "http.server", "8080"]
