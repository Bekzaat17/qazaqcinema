"""Подписанные ссылки на прослушивание в Mini App.

`<audio src>` не умеет слать заголовок авторизации, поэтому доступ к файлу даёт сама
ссылка: id трека + срок + HMAC. Ссылку выдаёт только авторизованная ручка, а чужой
сайт не может бесконечно качать каталог через наш сервер — подпись протухает.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta

STREAM_TTL = timedelta(hours=12)


def stream_signature(key: bytes, track_id: int, expires: int) -> str:
    message = f"{track_id}:{expires}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:32]


def stream_expiry(now: datetime) -> int:
    # Округление до часа: ответы одного часа дают одинаковую ссылку, и браузер берёт
    # трек из своего кэша, а не скачивает его заново при каждом обновлении списка.
    rounded = now.replace(minute=0, second=0, microsecond=0) + STREAM_TTL
    return int(rounded.timestamp())


def verify_stream(key: bytes, track_id: int, expires: int, signature: str, now: datetime) -> bool:
    if expires < now.timestamp():
        return False
    return hmac.compare_digest(stream_signature(key, track_id, expires), signature)
