# app/core/lifespan.py

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import settings
from app.services.importer import CsvTransactionImporter


@asynccontextmanager
async def lifespan(app: FastAPI):

    redis = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        username=settings.redis.username,
        password=settings.redis.password,
        decode_responses=settings.redis.decode_responses,
    )

    importer = CsvTransactionImporter(
        file_path=settings.csv_path,
        redis=redis,
        batch_size=settings.batch_size,
    )

    importer_task = asyncio.create_task(importer.run())

    def _log_result(task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print("IMPORTER CRASHED:", repr(exc))

    importer_task.add_done_callback(_log_result)

    try:
        yield
    finally:
        importer_task.cancel()
        await redis.close()
