"""Постер фильма: одна картинка от админа → две копии на диске.

Крупная (`POSTER`) нужна карточке фильма, hero главной и отправке файлом в канал.
Мелкая (`POSTER_THUMB`) — сеткам каталога и полкам: там постер занимает 110–190 px, а
крупная копия весит вдвое больше и на экране с двумя десятками карточек превращается в
мегабайты трафика и в декодирование прямо посреди скролла.

Обе копии режутся из ОРИГИНАЛА, а не мелкая из крупной: пересжатие уже сжатого JPEG
добавляет артефакты там, где их видно (текст на афише).

Сервис единственный, кто знает про эту пару, — и `MovieIngestionService`, и
`SeriesService` зовут его, а не хранилище напрямую. Иначе правило «постер = две копии»
пришлось бы помнить в каждом месте, где заводится фильм.
"""

from __future__ import annotations

from app.application.ports.images import POSTER, POSTER_THUMB, ImageProcessor
from app.application.ports.storage import PosterStorage


class PosterService:
    def __init__(self, images: ImageProcessor, posters: PosterStorage) -> None:
        self._images = images
        self._posters = posters

    async def store(self, raw: bytes) -> str:
        """Сохранить постер во всех размерах; вернуть URL крупной копии (он идёт в БД).

        URL мелкой копии в БД не хранится и наружу не отдаётся: он выводится из этого
        по правилу хранилища (см. `PosterStorage.save`), одинаково известному фронту.
        Битая картинка → ValueError из `ImageProcessor`, до диска дело не доходит.
        """
        full = await self._images.normalize(raw, POSTER)
        thumb = await self._images.normalize(raw, POSTER_THUMB)
        return await self._posters.save(full, thumb=thumb)
