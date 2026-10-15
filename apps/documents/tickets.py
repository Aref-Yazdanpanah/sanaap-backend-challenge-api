import secrets

import redis
from django.conf import settings
from django.core.cache import cache

PREFIX = "ws-ticket:"


def issue_ticket(user) -> str:
    ticket = secrets.token_urlsafe(32)
    cache.set(f"{PREFIX}{ticket}", user.pk, timeout=settings.WEBSOCKET_TICKET_TTL)
    return ticket


def consume_ticket(ticket: str):
    cache_key = f"{PREFIX}{ticket}"
    backend = settings.CACHES["default"]["BACKEND"]
    if backend == "django.core.cache.backends.redis.RedisCache":
        raw = redis.Redis.from_url(settings.REDIS_CACHE_URL).getdel(
            cache.make_key(cache_key)
        )
        if raw is None:
            return None
        return {"user_id": int(raw)}
    value = cache.get(cache_key)
    if value is not None:
        cache.delete(cache_key)
    return {"user_id": value} if value is not None else None
