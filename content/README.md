# Контент канала

Пул постов для `@qazaqcinema_kz` (PLAN.md §4). Один YAML на рубрику, картинки — в `images/`.
Формат элемента — в докстринге `app/infrastructure/content/yaml_loader.py`.
Заливка: `./start.sh seed` (идемпотентно, upsert по `slug`). Проверка без БД:
`python -m app.tools.seed_content --check`.
