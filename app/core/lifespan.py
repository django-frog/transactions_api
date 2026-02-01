# app/core/lifespan.py

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redis.asyncio import Redis
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.services.importer import CsvTransactionImporter
from app.services.aggregator import RedisAggregationWorker
from app.services.persistor import MongoPersistenceWorker

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Resource Initialization
    # We explicitly pull only connection params to avoid sending 'agg_prefix' to Redis client
    redis_params = {
        "host": settings.redis.host,
        "port": settings.redis.port,
        "password": settings.redis.password,
        "username": settings.redis.username,
        "decode_responses": settings.redis.decode_responses
    }
    
    redis_producer = Redis(**redis_params)
    redis_consumer = Redis(**redis_params)
    redis_persistor = Redis(**redis_params)

    mongo_client = AsyncIOMotorClient(settings.mongodb.uri)
    mongo_db = mongo_client[settings.mongodb.database]
    mongo_col = mongo_db[settings.mongodb.collection]

    # 2. Worker Initialization
    importer = CsvTransactionImporter(
        file_path=settings.csv_path,
        redis=redis_producer,
        batch_size=settings.batch_size,
    )

    aggregator = RedisAggregationWorker(
        redis=redis_consumer,
        stream_name="transactions",
        group_name="aggregators",
        consumer_name="aggregator-1",
        batch_size=50,
    )

    persistor = MongoPersistenceWorker(
        redis=redis_persistor,
        mongo_collection=mongo_col,
        retention_days=3,
        interval_seconds=10
    )

    # 3. Task Launch
    tasks = {
        "importer": asyncio.create_task(importer.run(), name="importer"),
        "aggregator": asyncio.create_task(aggregator.run(), name="aggregator"),
        "persistor": asyncio.create_task(persistor.run(), name="persistor"),
    }

    def _log_done(t: asyncio.Task):
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Background task %s failed", t.get_name())

    for t in tasks.values():
        t.add_done_callback(_log_done)

    try:
        yield
    finally:
        logger.info("Graceful shutdown initiated...")
        for name, task in tasks.items():
            task.cancel()
        
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        await redis_producer.close()
        await redis_consumer.close()
        mongo_client.close()
        logger.info("System offline.")