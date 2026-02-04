# app/core/lifespan.py

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.services.importer import CsvTransactionImporter
from app.services.aggregator import RedisAggregationWorker
from app.services.persistor import MongoPersistenceWorker
from app.infrastructure.redis import create_redis_client
from app.infrastructure.mongo import create_mongo_client

import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = logging.getLogger(__name__)

    logger.info("🚀 System starting (Batch Size: %d)", settings.batch_size)

    redis_params = {
        "host": settings.redis.host,
        "port": settings.redis.port,
        "password": settings.redis.password,
        "username": settings.redis.username,
        "decode_responses": settings.redis.decode_responses
    }

    # ----------------------------
    # Worker clients
    # ----------------------------
    redis_producer = create_redis_client(**redis_params)
    redis_consumer = create_redis_client(**redis_params)
    redis_persistor = create_redis_client(**redis_params)

    mongo_writer_client = create_mongo_client(settings.mongodb.uri)
    mongo_writer_db = mongo_writer_client[settings.mongodb.database]
    mongo_writer_col = mongo_writer_db[settings.mongodb.collection]

    # ----------------------------
    # API clients (read side)
    # ----------------------------
    redis_api = create_redis_client(**redis_params)

    mongo_reader_client = create_mongo_client(settings.mongodb.uri)
    mongo_reader_db = mongo_reader_client[settings.mongodb.database]
    mongo_reader_col = mongo_reader_db[settings.mongodb.collection]

    # expose ONLY API clients
    app.state.redis_api = redis_api
    app.state.mongo_api = mongo_reader_col

    # ----------------------------
    # Workers
    # ----------------------------
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
        mongo_collection=mongo_writer_col,
        retention_days=7,
        interval_seconds=10
    )

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

        for t in tasks.values():
            t.cancel()

        await asyncio.gather(*tasks.values(), return_exceptions=True)

        await redis_producer.close()
        await redis_consumer.close()
        await redis_persistor.close()
        await redis_api.close()

        mongo_writer_client.close()
        mongo_reader_client.close()

        logger.info("System offline.")
