import asyncio
import logging
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from redis.asyncio import Redis

from app.core.redis_keys import get_agg_key, get_tracked_days_key, get_virtual_clock_key

logger = logging.getLogger(__name__)

class MongoPersistenceWorker:
    def __init__(
        self,
        redis: Redis,
        mongo_collection: AsyncIOMotorCollection,
        interval_seconds: int = 10,
        retention_days: int = 7,
    ) -> None:
        self.redis = redis
        self.mongo = mongo_collection
        self.interval = interval_seconds
        self.retention_days = retention_days


    async def run(self) -> None:
        logger.info("Persistence worker started. Interval: %ds, Retention: %dd", self.interval, self.retention_days)
        
        while True:
            try:
                # We put the logic inside the try to ensure the loop keeps spinning
                await self._persist_historical_data()
            except asyncio.CancelledError:
                logger.info("Persistence worker received cancellation. Shutting down...")
                raise
            except Exception as e:
                # CRITICAL: Catch errors inside the loop so one failure doesn't stop the worker
                logger.error(f"Error during persistence cycle: {str(e)}", exc_info=True)
            
            # This must always happen to prevent a busy-loop if an error occurs instantly
            await asyncio.sleep(self.interval)

    async def _persist_historical_data(self) -> None:
        # Heartbeat log to prove the loop is spinning
        logger.debug("Persistor heartbeat: checking for data to archive...")
        
        raw_clock = await self.redis.get(get_virtual_clock_key())
        if not raw_clock:
            logger.info("Persistor: No virtual clock found yet.")
            return

        clock_str = raw_clock if isinstance(raw_clock, str) else raw_clock.decode()
        system_clock = datetime.fromisoformat(clock_str)
        boundary_date = (system_clock - timedelta(days=self.retention_days)).date()
        
        tracked_days = await self.redis.smembers(get_tracked_days_key())
        
        if not tracked_days:
            return

        for day_bytes in tracked_days:
            day_str = day_bytes if isinstance(day_bytes, str) else day_bytes.decode()
            current_day = datetime.fromisoformat(day_str).date()

            if current_day <= boundary_date:
                # Add a specific log before the network call to Mongo
                logger.info(f"Day {day_str} identified as historical. Moving...")
                await self._move_day_to_mongo(day_str)
                
                # Yield control after every single day migration
                await asyncio.sleep(0.01)

    async def _move_day_to_mongo(self, day_str: str) -> None:
        deposit_key = get_agg_key(day_str, "deposit")
        withdrawal_key = get_agg_key(day_str, "withdrawal")

        async with self.redis.pipeline() as pipe:
            pipe.hgetall(deposit_key)
            pipe.hgetall(withdrawal_key)
            deposits, withdrawals = await pipe.execute()

        if not deposits and not withdrawals:
            await self.redis.srem(get_tracked_days_key(), day_str)
            return

        update_payload = {}
        for method, val in deposits.items():
            m_name = method if isinstance(method, str) else method.decode()
            update_payload[f"deposits.{m_name}"] = round(float(val), 2)
            
        for method, val in withdrawals.items():
            m_name = method if isinstance(method, str) else method.decode()
            update_payload[f"withdrawals.{m_name}"] = round(float(val), 2)

        if update_payload:
            await self.mongo.update_one(
                {"date": day_str},
                {"$inc": update_payload, "$set": {"last_updated": datetime.now(timezone.utc)}},
                upsert=True
            )
            logger.info("Archived %s to MongoDB.", day_str)

        async with self.redis.pipeline() as pipe:
            pipe.delete(deposit_key, withdrawal_key)
            pipe.srem(get_tracked_days_key(), day_str)
            await pipe.execute()

            
