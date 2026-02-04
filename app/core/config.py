import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


# Load .env for local / docker parity
load_dotenv()


# ---------------------------------------------------------
# Public models
# ---------------------------------------------------------

class RedisSettings(BaseModel):
    host: str
    port: int
    username: str
    password: str
    decode_responses: bool = True

    # Discovery Keys
    tracked_days_key: str = "system:tracked_days"
    virtual_clock_key: str = "system:virtual_clock"

    # Key Prefix
    agg_prefix: str = "agg"


class MongoSettings(BaseModel):
    uri: str
    database: str
    collection: str


class AppSettings(BaseModel):
    redis: RedisSettings
    mongodb: MongoSettings
    csv_path: Path
    batch_size: int = 10
    log_level : str = 'INFO'


# ---------------------------------------------------------
# Loader
# ---------------------------------------------------------

def _get_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def load_settings() -> AppSettings:
    try:
        redis = RedisSettings(
            host=os.environ["REDIS_HOST"],
            port=int(os.environ.get("REDIS_PORT", 6379)),
            username=os.environ.get("REDIS_USERNAME", ""),
            password=os.environ.get("REDIS_PASSWORD", ""),
            decode_responses=_get_bool(
                os.environ.get("REDIS_DECODE_RESPONSES"),
                True,
            ),
            tracked_days_key=os.environ.get(
                "REDIS_TRACKED_DAYS_KEY",
                "system:tracked_days",
            ),
            virtual_clock_key=os.environ.get(
                "REDIS_VIRTUAL_CLOCK_KEY",
                "system:virtual_clock",
            ),
            agg_prefix=os.environ.get(
                "REDIS_AGG_PREFIX",
                "agg",
            ),
        )

        mongodb = MongoSettings(
            uri=os.environ["MONGODB_URI"],
            database=os.environ["MONGODB_DATABASE"],
            collection=os.environ["MONGODB_COLLECTION"],
        )

        return AppSettings(
            redis=redis,
            mongodb=mongodb,
            csv_path=Path(
                os.environ.get(
                    "CSV_PATH",
                    "app/sorted_transactions_1_month.csv",
                )
            ),
            batch_size=int(os.environ.get("BATCH_SIZE", 10)),
            log_level=os.environ.get("LOG_LEVEL", "INFO")
        )

    except KeyError as exc:
        raise RuntimeError(
            f"Missing required environment variable: {exc.args[0]}"
        ) from None


settings = load_settings()
