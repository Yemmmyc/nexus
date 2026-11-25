FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY app ./app

RUN groupadd --system nexus \
    && useradd --system --gid nexus nexus \
    && mkdir -p /app/data \
    && chown -R nexus:nexus /app

USER nexus

EXPOSE 8010

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/api/v1/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
