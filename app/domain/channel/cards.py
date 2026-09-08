"""Карточка-картинка поста: ЧТО на ней написано и как она выглядит — данные.

Портреты авторов сами по себе разные по цвету и кадру; чтобы лента канала читалась как
одно оформление, каждая карточка собирается по одному шаблону: тёмный сине-стальной фон
(в тон Mini App), круглый портрет в золотом кольце, рубрика капителями, крупный
заголовок, подпись автора и адрес канала. Размеры/цвета/шрифты — здесь; как это
нарисовать — `infrastructure/images/cards_pillow.py` (порт `CardRenderer`).

Генерируется на этапе заполнения (сидер), не при публикации: файлы лежат на диске,
их можно посмотреть глазами до того, как они уйдут подписчикам.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class CardSpec:
    title: str            # крупно: «Бірінші сөз» / текст цитаты у нақыл сөз
    portrait: str = ""    # путь к портрету относительно content/images/; пусто → инициал в круге
    label: str = ""       # рубрика капителями: «АБАЙДЫҢ ҚАРА СӨЗДЕРІ»
    subtitle: str = ""    # автор и годы: «Абай Құнанбайұлы · 1845–1904»


@dataclass(frozen=True, slots=True)
class CardStyle:
    width: int = 1280
    height: int = 720
    background_top: str = "#0B1F33"
    background_bottom: str = "#123B5C"
    accent: str = "#F2C14E"        # золото: кольцо портрета и рубрика
    text: str = "#FFFFFF"
    muted: str = "#B8C7D9"
    portrait_diameter: int = 400
    padding: int = 72
    title_size: int = 64
    label_size: int = 26
    subtitle_size: int = 30
    handle_size: int = 26
    # Адрес канала в подвале карточки. Пусто — подвала нет: конкретный @-хэндл живёт в
    # env (BOT_PUBLIC_CHANNEL_USERNAME), а не в коде домена.
    handle: str = ""
    quality: int = 88


DEFAULT_STYLE = CardStyle()


def style_for_channel(username: str) -> CardStyle:
    """Стиль с адресом канала из конфига. Канал не настроен → карточка без подвала."""
    handle = username.strip().lstrip("@")
    return replace(DEFAULT_STYLE, handle=f"@{handle}") if handle else DEFAULT_STYLE
