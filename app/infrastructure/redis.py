from redis.asyncio import Redis

def create_redis_client(**params) -> Redis:
    return Redis(**params)
