# app/core/lifespan.py

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import settings
from app.services.importer import CsvTransactionImporter
from app.services.aggregator import RedisAggregationWorker


@asynccontextmanager
async def lifespan(app: FastAPI):

    redis_producer = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        username=settings.redis.username,
        password=settings.redis.password,
        decode_responses=settings.redis.decode_responses,
    )

    redis_consumer = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        username=settings.redis.username,
        password=settings.redis.password,
        decode_responses=settings.redis.decode_responses,
    )

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

    importer_task = asyncio.create_task(importer.run(), name="csv-importer")
    aggregator_task = asyncio.create_task(aggregator.run(), name="aggregator")

    def _log_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            # keep logging consistent with your logging system
            import logging
            logging.getLogger(__name__).exception(
                "Background task crashed",
                exc_info=exc,
            )

    importer_task.add_done_callback(_log_result)
    aggregator_task.add_done_callback(_log_result)

    try:
        yield
    finally:
        importer_task.cancel()
        aggregator_task.cancel()

        await redis_producer.close()
        await redis_consumer.close()