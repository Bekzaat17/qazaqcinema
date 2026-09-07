"""`content/*.yaml` → `ContentItem` + картинки в `MEDIA_ROOT/channel/`.

Формат файла — список элементов:

```yaml
- slug: abai-qara-soz-01          # натуральный ключ (upsert), латиница/цифры/дефис
  kind: longread                  # форма: quiz_choice | quiz_open | longread | saying | term_list
  topic: abai                     # рубрика из topics.TOPICS
  title: Бірінші қара сөз
  body: |                          # текст (у квизов может отсутствовать)
    ...
  source: Абай Құнанбайұлы, «Қара сөздер»
  image: abai/portrait.jpg        # относительно content/images/; копируется в channel/<slug>.<ext>
  image_credit: Wikimedia Commons, public domain
  scheduled_for: 2027-03-22       # необязательный пин на дату
  payload:                        # по форме — см. item.py
    question: ...
    options: [...]
    answer: 0
```

Здесь только разбор и копирование файлов; проверка справочников — в `ContentSeedService`.
Ошибка формата — `SeedError` с указанием файла и slug: сидер останавливается, ничего не
записав (всё или ничего).
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml

from app.application.services.content_seed_service import SeedError
from app.domain.channel.content.item import (
    ContentItem,
    Payload,
    QuizChoice,
    QuizOpen,
    Term,
    TermList,
)
from app.domain.channel.content.kinds import ContentKind

CHANNEL_MEDIA_DIR = "channel"


def load_items(
    content_dir: Path, media_root: Path, *, copy_images: bool = True
) -> list[ContentItem]:
    """Все `*.yaml` каталога (по имени) → элементы. Картинки копируются в `media_root/channel/`."""
    items: list[ContentItem] = []
    for path in sorted(content_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            raise SeedError(f"{path.name}: ожидался список элементов")
        for index, entry in enumerate(raw):
            if not isinstance(entry, dict):
                raise SeedError(f"{path.name}[{index}]: элемент должен быть словарём")
            images_dir = content_dir / "images"
            items.append(
                _parse(cast(dict[str, Any], entry), path, images_dir, media_root, copy_images)
            )
    return items


def _parse(
    entry: dict[str, Any], path: Path, images_dir: Path, media_root: Path, copy_images: bool
) -> ContentItem:
    slug = str(entry.get("slug", "")).strip()
    where = f"{path.name}:{slug or '?'}"
    if not slug or not all(ch.isalnum() or ch in "-_" for ch in slug):
        raise SeedError(f"{where}: slug обязателен (латиница/цифры/дефис)")
    try:
        kind = ContentKind(str(entry["kind"]))
    except (KeyError, ValueError) as exc:
        raise SeedError(f"{where}: неизвестная форма kind={entry.get('kind')!r}") from exc
    topic = str(entry.get("topic", "")).strip()
    if not topic:
        raise SeedError(f"{where}: topic обязателен")

    payload = _payload(kind, entry.get("payload"), where)
    image_path = _image(entry.get("image"), slug, images_dir, media_root, copy_images, where)
    scheduled = entry.get("scheduled_for")
    if scheduled is not None and not isinstance(scheduled, date):
        raise SeedError(f"{where}: scheduled_for должен быть датой YYYY-MM-DD")

    return ContentItem(
        slug=slug,
        kind=kind,
        topic=topic,
        title_kk=str(entry.get("title", "")).strip(),
        body_kk=str(entry.get("body", "")).strip(),
        source=str(entry.get("source", "")).strip(),
        image_path=image_path,
        image_credit=str(entry.get("image_credit", "")).strip(),
        payload=payload,
        scheduled_for=scheduled,
        is_active=bool(entry.get("active", True)),
    )


def _payload(kind: ContentKind, raw: object, where: str) -> Payload:
    if raw is None:
        if kind.is_quiz or kind is ContentKind.TERM_LIST:
            raise SeedError(f"{where}: форма {kind} требует payload")
        return None
    if not isinstance(raw, dict):
        raise SeedError(f"{where}: payload должен быть словарём")
    data = cast(dict[str, Any], raw)
    try:
        match kind:
            case ContentKind.QUIZ_CHOICE:
                return QuizChoice(
                    question=str(data["question"]).strip(),
                    options=tuple(str(o).strip() for o in data["options"]),
                    answer=int(data["answer"]),
                )
            case ContentKind.QUIZ_OPEN:
                return QuizOpen(
                    question=str(data["question"]).strip(),
                    accept=tuple(str(a).strip() for a in data["accept"]),
                )
            case ContentKind.TERM_LIST:
                return TermList(
                    items=tuple(
                        Term(str(t["term"]).strip(), str(t["meaning"]).strip())
                        for t in data["items"]
                    ),
                    note=str(data.get("note", "")).strip(),
                )
            case _:
                raise SeedError(f"{where}: у формы {kind} payload не бывает")
    except (KeyError, TypeError, ValueError) as exc:
        raise SeedError(f"{where}: битый payload — {exc}") from exc


def _image(
    raw: object, slug: str, images_dir: Path, media_root: Path, copy_images: bool, where: str
) -> str | None:
    """Копия картинки под именем slug в `channel/` тома: имя стабильно, повторный сидер
    перезаписывает файл на месте."""
    if raw is None:
        return None
    src = images_dir / str(raw)
    if not src.is_file():
        raise SeedError(f"{where}: картинка {src} не найдена")
    rel = f"{CHANNEL_MEDIA_DIR}/{slug}{src.suffix.lower()}"
    if copy_images:
        dest = media_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return rel
