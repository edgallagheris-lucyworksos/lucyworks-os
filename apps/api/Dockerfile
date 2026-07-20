FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system lucyworks && useradd --system --gid lucyworks --home-dir /app lucyworks \
    && apt-get update \
    && apt-get install --no-install-recommends -y curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip -q && pip install -r requirements.txt

COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod 0555 ./docker-entrypoint.sh && chown -R lucyworks:lucyworks /app

USER lucyworks
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=5 CMD curl -fsS http://127.0.0.1:8000/api/health/live || exit 1
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
