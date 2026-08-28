FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY assets ./assets

RUN mkdir -p storage logs

EXPOSE 8000

# The worker image overrides this with the celery command (see docker-compose.yml).
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]