# Контент канала

Пул постов для `@qazaqcinema_kz`: один YAML на рубрику, картинки — в `images/`, шрифты для
карточек — в `fonts/`. `holidays.yaml` — поздравления с праздниками: slug элемента = slug
праздника из `app/domain/channel/holidays.py`, иначе поздравление не найдётся (тест
`tests/test_holidays.py` это проверяет). Формат элемента — в докстринге
`app/infrastructure/content/yaml_loader.py`; сетка слотов и ротация — в
`app/domain/channel/content/plan.py` (см. CLAUDE.md, «Публичный канал»).

Заливка: `./start.sh seed` (идемпотентно, upsert по `slug`).
Проверка YAML без БД: `./start.sh seed --check`.
