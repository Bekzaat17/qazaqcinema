FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Сначала метаданные + пакет (для установки зависимостей), потом остальное
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY migrations ./migrations
COPY alembic.ini ./

# По умолчанию — бот (polling). API переопределяет команду в docker-compose.
CMD ["python", "-m", "app.main"]
