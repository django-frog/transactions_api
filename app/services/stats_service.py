from datetime import date, datetime, timedelta
from typing import Iterable
import logging

from motor.motor_asyncio import AsyncIOMotorCollection
from redis.asyncio import Redis

from app.core.redis_keys import get_agg_key, get_virtual_clock_key


logger = logging.getLogger(__name__)


class StatsQueryService:

    def __init__(
        self,
        redis: Redis,
        mongo: AsyncIOMotorCollection,
        hot_days: int = 7,
    ):
        self.redis = redis
        self.mongo = mongo
        self.hot_days = hot_days

    async def get_range(self, start: date, end: date) -> dict[str, dict]:
        days = list(self._date_range(start, end))

        hot_boundary, virtual_today = await self._get_hot_boundary()

        redis_days = [d for d in days if d >= hot_boundary]
        mongo_days = [d for d in days if d < hot_boundary]

        logger.info(
            "Stats query [%s -> %s] | virtual_today=%s | hot_boundary=%s | redis_days=%d | mongo_days=%d",
            start,
            end,
            virtual_today,
            hot_boundary,
            len(redis_days),
            len(mongo_days),
        )

        result: dict[str, dict] = {}

        if redis_days:
            redis_data = await self._read_many_from_redis(redis_days)
            logger.info(
                "Stats query: fetched %d days from Redis",
                len(redis_data),
            )
            result.update(redis_data)

        if mongo_days:
            mongo_data = await self._read_many_from_mongo(mongo_days)
            logger.info(
                "Stats query: fetched %d days from MongoDB",
                len(mongo_data),
            )
            result.update(mongo_data)

        logger.info(
            "Stats query finished | total_returned_days=%d",
            len(result),
        )

        return result

    # ---------------------------------------------------------
    # Redis
    # ---------------------------------------------------------

    async def _read_many_from_redis(
        self,
        days: list[date],
    ) -> dict[str, dict]:

        logger.debug(
            "Reading %d days from Redis (pipeline)",
            len(days),
        )

        pipe = self.redis.pipeline()

        for d in days:
            day_str = d.isoformat()
            dep_key = get_agg_key(day_str, "deposit")
            wit_key = get_agg_key(day_str, "withdrawal")

            pipe.hgetall(dep_key)
            pipe.hgetall(wit_key)

        raw = await pipe.execute()

        result: dict[str, dict] = {}

        i = 0
        for d in days:
            dep = raw[i]
            wit = raw[i + 1]
            i += 2

            if not dep and not wit:
                continue

            result[d.isoformat()] = {
                "deposits": {k: float(v) for k, v in dep.items()},
                "withdrawals": {k: float(v) for k, v in wit.items()},
            }

        return result

    # ---------------------------------------------------------
    # Mongo
    # ---------------------------------------------------------

    async def _read_many_from_mongo(
        self,
        days: list[date],
    ) -> dict[str, dict]:

        logger.debug(
            "Reading %d days from MongoDB (single query)",
            len(days),
        )

        day_strings = [d.isoformat() for d in days]

        cursor = self.mongo.find(
            {"date": {"$in": day_strings}},
            {"_id": 0, "date": 1, "deposits": 1, "withdrawals": 1},
        )

        result: dict[str, dict] = {}

        async for doc in cursor:
            result[doc["date"]] = {
                "deposits": doc.get("deposits", {}),
                "withdrawals": doc.get("withdrawals", {}),
            }

        return result

    # ---------------------------------------------------------
    # Utils
    # ---------------------------------------------------------

    def _date_range(self, start: date, end: date) -> Iterable[date]:
        current = start
        while current <= end:
            yield current
            current += timedelta(days=1)

    # ---------------------------------------------------------
    # Virtual clock
    # ---------------------------------------------------------

    async def _get_hot_boundary(self) -> tuple[date, date]:
        raw = await self.redis.get(get_virtual_clock_key())

        if not raw:
            virtual_today = date.today()
            hot_boundary = virtual_today - timedelta(days=self.hot_days)

            logger.warning(
                "Virtual clock not found in Redis – falling back to system date (%s)",
                virtual_today,
            )

            return hot_boundary, virtual_today

        if isinstance(raw, bytes):
            raw = raw.decode()

        virtual_today = datetime.fromisoformat(raw).date()
        hot_boundary = virtual_today - timedelta(days=self.hot_days)

        logger.debug(
            "Virtual clock loaded: virtual_today=%s hot_boundary=%s",
            virtual_today,
            hot_boundary,
        )

        return hot_boundary, virtual_today
