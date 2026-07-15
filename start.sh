#!/usr/bin/env bash
# ============================================================================
# QazaqCinema — единая точка запуска. Весь стек в Docker: postgres, redis,
# migrate (авто-миграции), api, bot, web (nginx). ОДНА топология для всех сред —
# отличие dev/prod ТОЛЬКО в env-файле (12-factor).
#
#   ./start.sh              # = dev (локально), env = .env
#   ./start.sh dev          # то же самое явно
#   ./start.sh prod         # те же контейнеры, env = .env.prod
#   ./start.sh test         # ruff + mypy + pytest В КОНТЕЙНЕРЕ (env = .env.test, изолированная БД)
#   ./start.sh migrate      # применить миграции (alembic upgrade head) и выйти
#   ./start.sh backup       # дамп БД в backups/ (pg_dump|gzip, ротация 14; для cron на VPS)
#   ./start.sh logs [svc]   # логи всех сервисов или одного (Ctrl-C — выйти)
#   ./start.sh ps           # статус контейнеров
#   ./start.sh down         # остановить стек (данные в томах сохраняются)
#   ./start.sh down --clean # остановить + СТЕРЕТЬ тома (БД и постеры удалятся)
#
# Web → http://localhost/ , API/docs → http://localhost:8000/docs (127.0.0.1).
# Нет env-файла — создаётся из *.example (для prod после копирования впиши секреты).
# Хочешь hot-reload на время активной разработки — гоняй бэкенд на хосте из .venv
# (uvicorn --reload / python -m app.main) поверх поднятых ./start.sh контейнеров.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

# --- логи --------------------------------------------------------------------
if [ -t 1 ]; then C_G=$'\033[32m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_0=$'\033[0m'
else C_G=""; C_Y=""; C_R=""; C_0=""; fi
info() { printf '%s\n' "${C_G}▸${C_0} $*"; }
warn() { printf '%s\n' "${C_Y}⚠${C_0}  $*" >&2; }
die()  { printf '%s\n' "${C_R}✖${C_0} $*" >&2; exit 1; }

# --- предусловия -------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker не установлен. Поставь Docker Desktop и повтори."
docker info >/dev/null 2>&1       || die "Docker daemon не запущен. Открой Docker Desktop и повтори."
if docker compose version >/dev/null 2>&1; then DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then DC=(docker-compose)
else die "Нужен docker compose v2 (в составе Docker Desktop) или docker-compose."; fi

# dc <env-file> <args...> — docker compose с нужным env-файлом. ENV_FILE идёт и в
# интерполяцию ${...}, и в env_file: сервисов (одна топология, один compose-файл).
dc() { local ef="$1"; shift; ENV_FILE="$ef" "${DC[@]}" --env-file "$ef" -f docker-compose.yml "$@"; }

# ensure_env <target> <example> <strict:0|1>. Нет target — создаём из example.
ensure_env() {
  local target="$1" example="$2" strict="${3:-0}"
  [ -f "$target" ] && return 0
  [ -f "$example" ] || die "Нет ни $target, ни шаблона $example."
  cp "$example" "$target"
  if [ "$strict" = "1" ]; then
    die "Создал $target из $example — впиши секреты (BOT_TOKEN, DB_PASSWORD, …) и запусти снова."
  fi
  warn "Создал $target из $example. Для рабочего бота впиши BOT_TOKEN и BOT_ADMIN_* в $target."
}

up_stack() {  # $1 — env-файл
  info "Стек (postgres, redis, migrate, api, bot, web) — сборка и запуск в фоне…"
  dc "$1" up --build -d
  info "Готово. Web → http://localhost/   API → http://localhost:8000/docs"
  info "Логи: ./start.sh logs   |   Стоп: ./start.sh down"
}

# env-файл для сервисных команд (down/logs/ps/migrate) — любой валидный.
default_env() { [ -f .env ] && echo .env || echo .env.example; }

MODE="${1:-dev}"; [ $# -gt 0 ] && shift || true

case "$MODE" in
  dev)
    ensure_env .env .env.example 0
    up_stack .env
    ;;

  prod)
    ensure_env .env.prod .env.prod.example 1
    up_stack .env.prod
    ;;

  test)
    [ -f .env.test ] || die "Нет .env.test (должен лежать в репозитории)."
    info "TEST: поднимаю postgres (изолированная тест-БД)…"
    dc .env.test up -d postgres
    info "Жду готовности БД…"
    for _ in $(seq 1 30); do
      dc .env.test exec -T postgres pg_isready -U qazaqcinema >/dev/null 2>&1 && break
      sleep 1
    done
    test_db="$(grep -E '^DB_NAME=' .env.test | cut -d= -f2)"
    case "$test_db" in                        # защита: тесты дропают схему → только в _test-БД
      *_test) : ;;
      *) die "DB_NAME='$test_db' в .env.test не оканчивается на _test — отказ (защита рабочей БД).";;
    esac
    if dc .env.test exec -T postgres createdb -U qazaqcinema "$test_db" >/dev/null 2>&1; then
      info "Создал тест-БД $test_db"
    fi
    info "ruff + mypy + pytest (в контейнере, БД $test_db)…"
    dc .env.test run --rm --build test
    info "Тесты прошли. (Стек не гасил; ./start.sh down чтобы остановить.)"
    ;;

  migrate)
    ef="$(default_env)"
    info "Применяю миграции (alembic upgrade head)…"
    dc "$ef" run --rm migrate
    ;;

  backup)
    # Дамп рабочей БД из контейнера postgres. Env-файл: .env.prod (прод), иначе default.
    ef=".env.prod"; [ -f "$ef" ] || ef="$(default_env)"
    db_user="$(grep -E '^DB_USER=' "$ef" | cut -d= -f2)"; db_user="${db_user:-qazaqcinema}"
    db_name="$(grep -E '^DB_NAME=' "$ef" | cut -d= -f2)"; db_name="${db_name:-qazaqcinema}"
    mkdir -p backups
    out="backups/${db_name}-$(date +%Y%m%d-%H%M%S).sql.gz"
    info "Бэкап БД '$db_name' → $out"
    dc "$ef" exec -T postgres pg_dump -U "$db_user" "$db_name" | gzip > "$out"
    [ -s "$out" ] || { rm -f -- "$out"; die "Пустой дамп — postgres поднят? (./start.sh ps)"; }
    # Ротация по ВОЗРАСТУ (14 дней), а не по счётчику: ручные дампы перед обновлением
    # (DEPLOY.md §7) иначе вытесняли бы суточные и оставляли меньше 14 дней истории.
    # Чистим только после проверки дампа выше → без свежей копии ничего не удаляем.
    find backups -type f -name "${db_name}-*.sql.gz" -mtime +14 -delete 2>/dev/null || true
    info "Готово: $out ($(du -h "$out" | cut -f1))"
    ;;

  logs) dc "$(default_env)" logs -f "$@" ;;
  ps)   dc "$(default_env)" ps "$@" ;;

  down)
    ef="$(default_env)"
    if [ "${1:-}" = "--clean" ]; then
      warn "Останавливаю стек и УДАЛЯЮ тома (БД и постеры будут стёрты)."
      dc "$ef" down -v --remove-orphans
    else
      dc "$ef" down --remove-orphans
    fi
    ;;

  -h|--help|help)
    sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'
    ;;

  *) die "Неизвестный режим: '$MODE'. Запусти ./start.sh help для списка команд." ;;
esac
