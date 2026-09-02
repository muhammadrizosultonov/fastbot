from redis.asyncio import Redis


def create_redis(url: str) -> Redis:
    return Redis.from_url(url, encoding="utf-8", decode_responses=True, health_check_interval=30)
