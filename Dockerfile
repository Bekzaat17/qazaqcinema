# Многостадийный образ бэкенда.
#   runtime — прод/дев/тест-стек: только рантайм-зависимости (лёгкий образ api/bot/migrate).
#   test    — runtime + dev-инструменты (ruff/mypy/pytest) + tests/ (для ./start.sh test).
# Прод и дев берут ОДИН и тот же образ (стадия runtime) — отличие сред только в env-файле.
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Сначала метаданные + пакет (кэш слоя зависимостей), потом остальное.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY migrations ./migrations
COPY alembic.ini ./

# По умолчанию — бот (polling). api/migrate переопределяют command в docker-compose.
CMD ["python", "-m", "app.main"]

# --- тестовый образ (в проде не участвует) ----------------------------------
FROM runtime AS test
RUN pip install --no-cache-dir ".[dev]"
COPY tests ./tests
CMD ["pytest"]
