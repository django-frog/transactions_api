import asyncio
import logging
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from app.core.redis_keys import get_agg_key, get_tracked_days_key, get_virtual_clock_key

logger = logging.getLogger(__name__)

class RedisAggregationWorker:
    def __init__(
        self,
        redis: Redis,
        stream_name: str = "transactions",
        group_name: str = "aggregators",
        consumer_name: str = "aggregator-1",
        batch_size: int = 50,
        block_ms: int = 5_000,
    ) -> None:
        self.redis = redis
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.local_virtual_clock: datetime | None = None

    async def run(self) -> None:
        await self._ensure_group()
        
        # Initialize clock using Shared Contract
        raw_clock = await self.redis.get(get_virtual_clock_key())
        if raw_clock:
            clock_str = raw_clock if isinstance(raw_clock, str) else raw_clock.decode()
            self.local_virtual_clock = datetime.fromisoformat(clock_str)
        
        logger.info(
            "Worker started. Group: %s, Clock: %s",
            self.group_name, self.local_virtual_clock,
        )

        try:
            while True:
                response = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: ">"},
                    count=self.batch_size,
                    block=self.block_ms,
                )

                if not response:
                    continue

                await self._handle_batch(response)

        except asyncio.CancelledError:
            logger.info("Aggregation worker shut down.")
            raise
        except Exception:
            logger.exception("Aggregation worker encountered a fatal error")
            raise

    async def _handle_batch(self, response: list[Any]) -> None:
        pipe = self.redis.pipeline()
        processed_count = 0
        
        for _, messages in response:
            for message_id, payload in messages:
                try:
                    ts = datetime.fromisoformat(payload["timestamp"])
                    day = ts.date().isoformat()
                    tx_type = payload["type"]
                    method = payload["payment_method"]
                    amount = round(float(payload["amount"]), 2)

                    # Aggregate via Shared Contract
                    agg_key = get_agg_key(day, tx_type)
                    pipe.hincrbyfloat(agg_key, method, amount)

                    # Register Day via Shared Contract
                    pipe.sadd(get_tracked_days_key(), day)

                    # Virtual Clock via Shared Contract
                    if self.local_virtual_clock is None or ts > self.local_virtual_clock:
                        self.local_virtual_clock = ts
                        pipe.set(get_virtual_clock_key(), ts.isoformat())

                    pipe.xack(self.stream_name, self.group_name, message_id)
                    processed_count += 1
                    
                except Exception:
                    logger.exception("Skipping malformed message: %s", message_id)
                    continue

        await pipe.execute()
        logger.info("Aggregated %d transactions. Clock: %s", processed_count, self.local_virtual_clock)

    async def _ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                name=self.stream_name, groupname=self.group_name, id="0", mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise