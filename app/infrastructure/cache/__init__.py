"""Redis-адаптеры инфраструктуры кэша/координации.

Реализации портов `Lock`/`RateLimiter` (и позже `SessionStore`/`CatalogCache`)
поверх `redis.asyncio`. Namespace-префиксы ключей (`lock:`, `ratelimit:`, …) живут
здесь — это Redis-концерн, домен/сервисы про них не знают.
"""
