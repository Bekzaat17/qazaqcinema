"""Pillow-реализация `CardRenderer` — карточка поста по шаблону `domain/channel/cards`.

Шрифт — Inter (OFL, лежит в `content/fonts/`): тот же, что во фронте, покрывает казахскую
кириллицу (ә ғ қ ң ө ұ ү і). Системных шрифтов в slim-образе нет, поэтому путь к папке со
шрифтами приходит явно.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.domain.channel.cards import DEFAULT_STYLE, CardSpec, CardStyle

_FONT_REGULAR = "Inter-Regular.ttf"
_FONT_BOLD = "Inter-Bold.ttf"
_FONT_SEMIBOLD = "Inter-SemiBold.ttf"


def _hex(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


class PillowCardRenderer:
    def __init__(self, fonts_dir: Path, style: CardStyle = DEFAULT_STYLE) -> None:
        self._fonts = fonts_dir
        self._style = style

    def _font(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(self._fonts / name), size)

    def render(self, spec: CardSpec, portrait: bytes | None) -> bytes:
        st = self._style
        canvas = self._background()
        draw = ImageDraw.Draw(canvas)

        # Портрет: круг в золотом кольце, слева по центру.
        cx = st.padding + st.portrait_diameter // 2
        cy = st.height // 2
        if portrait is not None:
            self._paste_portrait(canvas, portrait, (cx, cy))
        else:
            self._paste_initial(canvas, spec, (cx, cy))

        # Текстовый блок справа от портрета.
        x = st.padding * 2 + st.portrait_diameter
        width = st.width - x - st.padding
        y = st.padding + 24
        if spec.label:
            draw.text((x, y), spec.label.upper(), font=self._font(_FONT_SEMIBOLD, st.label_size),
                      fill=_hex(st.accent))
            y += st.label_size + 28

        # Подвал (черта + адрес) — фиксированная зона снизу; текст должен уложиться выше неё.
        footer_top = st.height - st.padding - st.handle_size - 18 - 24
        subtitle_block = st.subtitle_size + 18 if spec.subtitle else 0
        title_size = st.title_size
        title_font = self._font(_FONT_BOLD, title_size)
        lines = self._wrap(draw, spec.title, title_font, width)
        # Длинную цитату ужимаем шрифтом, а не режем: обрывать фразу посреди слова хуже
        # мелкой строки. Критерий — ВЫСОТА блока (строки × интерлиньяж + подпись), а не
        # число строк: шесть коротких строк влезают, шесть длинных при 64px — нет.
        while title_size > 26 and (
            y + len(lines) * int(title_size * 1.2) + subtitle_block > footer_top
        ):
            title_size -= 4
            title_font = self._font(_FONT_BOLD, title_size)
            lines = self._wrap(draw, spec.title, title_font, width)
        line_height = int(title_size * 1.2)
        for line in lines:
            draw.text((x, y), line, font=title_font, fill=_hex(st.text))
            y += line_height

        if spec.subtitle:
            y += 18
            draw.text((x, y), spec.subtitle, font=self._font(_FONT_REGULAR, st.subtitle_size),
                      fill=_hex(st.muted))

        # Адрес канала — внизу справа, золотая черта над ним как единый «подвал».
        # Канал не настроен (`style.handle` пуст) → подвала нет.
        if st.handle:
            handle_font = self._font(_FONT_SEMIBOLD, st.handle_size)
            handle_w = draw.textlength(st.handle, font=handle_font)
            hy = st.height - st.padding - st.handle_size
            draw.line([(x, hy - 18), (st.width - st.padding, hy - 18)],
                      fill=_hex(st.accent), width=2)
            draw.text((st.width - st.padding - handle_w, hy), st.handle, font=handle_font,
                      fill=_hex(st.muted))

        out = BytesIO()
        canvas.convert("RGB").save(out, format="JPEG", quality=st.quality, optimize=True)
        return out.getvalue()

    def _background(self) -> Image.Image:
        """Вертикальный градиент сверху вниз."""
        st = self._style
        top, bottom = _hex(st.background_top), _hex(st.background_bottom)
        column = Image.new("RGB", (1, st.height))
        for y in range(st.height):
            t = y / max(st.height - 1, 1)
            pixel = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))
            column.putpixel((0, y), pixel)
        return column.resize((st.width, st.height))

    def _paste_portrait(self, canvas: Image.Image, data: bytes, center: tuple[int, int]) -> None:
        st = self._style
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except (OSError, ValueError) as exc:
            raise ValueError("не удалось декодировать портрет") from exc
        d = st.portrait_diameter
        rgb = image.convert("RGB")
        if rgb.height > rgb.width * 1.25:
            # Явно вертикальный (поясной/групповой) снимок: лицо в верхней трети. Берём
            # квадрат по верхней части кадра — лицо крупно, без соседей по фото.
            side = min(rgb.width, int(rgb.height * 0.62))
            left = (rgb.width - side) // 2
            rgb = rgb.crop((left, 0, left + side, side))
        # Иначе (уже вырезанное лицо, квадрат) — обычный центр-кроп.
        fitted = ImageOps.fit(rgb, (d, d), method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (d * 4, d * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=255)
        mask = mask.resize((d, d), Image.Resampling.LANCZOS)  # сглаженный край

        cx, cy = center
        ring = 6
        ImageDraw.Draw(canvas).ellipse(
            (cx - d // 2 - ring, cy - d // 2 - ring, cx + d // 2 + ring, cy + d // 2 + ring),
            fill=_hex(st.accent),
        )
        canvas.paste(fitted, (cx - d // 2, cy - d // 2), mask)

    def _paste_initial(self, canvas: Image.Image, spec: CardSpec, center: tuple[int, int]) -> None:
        """Нет открытого портрета → золотой круг с первой буквой подписи (или заголовка)."""
        st = self._style
        d = st.portrait_diameter
        cx, cy = center
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2), fill=_hex(st.accent))
        source = spec.subtitle or spec.title
        letter = next((ch for ch in source if ch.isalpha()), "•").upper()
        font = self._font(_FONT_BOLD, int(d * 0.5))
        box = draw.textbbox((0, 0), letter, font=font)
        w, h = box[2] - box[0], box[3] - box[1]
        draw.text((cx - w / 2 - box[0], cy - h / 2 - box[1]), letter, font=font,
                  fill=_hex(st.background_top))

    @staticmethod
    def _wrap(
        draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int
    ) -> list[str]:
        lines: list[str] = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split():
                candidate = f"{current} {word}".strip()
                if draw.textlength(candidate, font=font) <= width or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines
