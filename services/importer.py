import asyncio
import logging
from pathlib import Path
from typing import Any

import aiofiles
from redis.asyncio import Redis


logger = logging.getLogger(__name__)


class CsvTransactionImporter:

    def __init__(
        self,
        file_path: Path,
        redis: Redis,
        batch_size: int = 10,
    ) -> None:

        if not file_path.exists():
            raise RuntimeError(f"CSV file not found: {file_path}")

        self.file_path = file_path
        self.redis = redis
        self.batch_size = batch_size

        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=batch_size * 2
        )

    async def run(self) -> None:
        logger.info(
            "CSV importer started",
            extra={
                "file": str(self.file_path),
                "batch_size": self.batch_size,
            },
        )

        workers = [
            asyncio.create_task(self._worker(i), name=f"csv-worker-{i}")
            for i in range(self.batch_size)
        ]

        try:
            await self._producer()
            await self._queue.join()

            logger.info("CSV importer finished successfully")

        except asyncio.CancelledError:
            logger.info("CSV importer cancelled")
            raise

        except Exception:
            logger.exception("CSV importer crashed")
            raise

        finally:
            for w in workers:
                w.cancel()

    # -------------------------------------
    # Producer – strictly sequential reader
    # -------------------------------------
    async def _producer(self) -> None:
        logger.info("CSV producer started")

        produced = 0

        async with aiofiles.open(self.file_path, mode="r") as f:
            header: list[str] | None = None

            async for line in f:
                line = line.rstrip("\n")

                if not line:
                    continue

                if header is None:
                    header = line.split(",")
                    logger.debug("CSV header loaded: %s", header)
                    continue

                values = line.split(",")
                row = dict(zip(header, values))

                await self._queue.put(row)
                produced += 1

                if produced % 1_000 == 0:
                    logger.info("Produced %d rows", produced)

        logger.info("CSV producer finished. Total rows: %d", produced)

    # -------------------------------------
    # Workers – concurrent bounded senders
    # -------------------------------------
    async def _worker(self, worker_id: int) -> None:
        logger.debug("Worker %s started", worker_id)

        try:
            while True:
                row = await self._queue.get()
                try:
                    await self._process_row(row, worker_id)
                finally:
                    self._queue.task_done()

        except asyncio.CancelledError:
            logger.debug("Worker %s cancelled", worker_id)
            raise

    async def _process_row(
        self,
        row: dict[str, Any],
        worker_id: int,
    ) -> None:
        try:
            sleep_ms = int(row["sleep_ms"])
        except Exception:
            logger.warning(
                "Invalid sleep_ms value: %r (row=%r)",
                row.get("sleep_ms"),
                row,
            )
            return

        await asyncio.sleep(sleep_ms / 1000)

        try:
            await self.redis.xadd("transactions", row)

        except Exception:
            logger.exception(
                "Failed to push transaction to redis (worker=%s, timestamp=%s)",
                worker_id,
                row.get("timestamp"),
            )
            return

        logger.debug(
            "Transaction pushed (worker=%s, timestamp=%s)",
            worker_id,
            row.get("timestamp"),
        )
