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
  # ЛИБО карточка, собранная кодом (portrait — относительно content/images/):
  card: {portrait: authors/abai.jpg, label: Абайдың қара сөздері, subtitle: Абай Құнанбайұлы}
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

from app.application.ports.cards import CardRenderer
from app.application.services.content_seed_service import SeedError
from app.domain.channel.cards import CardSpec
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
    content_dir: Path,
    media_root: Path,
    cards: CardRenderer | None = None,
    *,
    copy_images: bool = True,
) -> list[ContentItem]:
    """Все `*.yaml` каталога (по имени) → элементы. Картинки копируются, карточки
    генерируются в `media_root/channel/`. `copy_images=False` — только проверка (диск не
    трогаем; карточки при этом всё равно рендерятся в память — ловим битые портреты)."""
    items: list[ContentItem] = []
    ctx = _Ctx(content_dir / "images", media_root, cards, copy_images)
    for path in sorted(content_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            raise SeedError(f"{path.name}: ожидался список элементов")
        for index, entry in enumerate(raw):
            if not isinstance(entry, dict):
                raise SeedError(f"{path.name}[{index}]: элемент должен быть словарём")
            items.append(_parse(cast(dict[str, Any], entry), path, ctx))
    return items


class _Ctx:
    def __init__(
        self, images_dir: Path, media_root: Path, cards: CardRenderer | None, copy_images: bool
    ) -> None:
        self.images_dir = images_dir
        self.media_root = media_root
        self.cards = cards
        self.copy_images = copy_images


def _parse(entry: dict[str, Any], path: Path, ctx: _Ctx) -> ContentItem:
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
    title = str(entry.get("title", "")).strip()
    if entry.get("image") is not None and entry.get("card") is not None:
        raise SeedError(f"{where}: image и card вместе не бывают — одно из двух")
    image_path = _image(entry.get("image"), slug, ctx, where)
    if entry.get("card") is not None:
        image_path = _card(entry["card"], slug, title, ctx, where)
    scheduled = entry.get("scheduled_for")
    if scheduled is not None and not isinstance(scheduled, date):
        raise SeedError(f"{where}: scheduled_for должен быть датой YYYY-MM-DD")

    return ContentItem(
        slug=slug,
        kind=kind,
        topic=topic,
        title_kk=title,
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


def _image(raw: object, slug: str, ctx: _Ctx, where: str) -> str | None:
    """Копия картинки под именем slug в `channel/` тома: имя стабильно, повторный сидер
    перезаписывает файл на месте."""
    if raw is None:
        return None
    src = ctx.images_dir / str(raw)
    if not src.is_file():
        raise SeedError(f"{where}: картинка {src} не найдена")
    rel = f"{CHANNEL_MEDIA_DIR}/{slug}{src.suffix.lower()}"
    if ctx.copy_images:
        dest = ctx.media_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return rel


def _card(raw: object, slug: str, title: str, ctx: _Ctx, where: str) -> str:
    """Карточка по шаблону (`domain/channel/cards`): портрет + подписи → `channel/<slug>.jpg`."""
    if not isinstance(raw, dict):
        raise SeedError(f"{where}: card должен быть словарём")
    data = cast(dict[str, Any], raw)
    portrait = ctx.images_dir / str(data.get("portrait", ""))
    if not portrait.is_file():
        raise SeedError(f"{where}: портрет {portrait} не найден")
    if ctx.cards is None:
        raise SeedError(f"{where}: карточки требуют генератор (CardRenderer), а он не передан")
    spec = CardSpec(
        title=str(data.get("title", title)).strip(),
        portrait=str(data["portrait"]),
        label=str(data.get("label", "")).strip(),
        subtitle=str(data.get("subtitle", "")).strip(),
    )
    if not spec.title:
        raise SeedError(f"{where}: у карточки пустой заголовок (нет ни card.title, ни title)")
    try:
        jpeg = ctx.cards.render(spec, portrait.read_bytes())
    except ValueError as exc:
        raise SeedError(f"{where}: {exc}") from exc
    rel = f"{CHANNEL_MEDIA_DIR}/{slug}.jpg"
    if ctx.copy_images:
        dest = ctx.media_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(jpeg)
    return rel
