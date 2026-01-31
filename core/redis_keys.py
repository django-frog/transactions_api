from app.core.config import settings

def get_tracked_days_key() -> str:
    return settings.redis.tracked_days_key

def get_virtual_clock_key() -> str:
    return settings.redis.virtual_clock_key

def get_agg_key(day: str, tx_type: str) -> str:
    """
    Standardizes the key format: agg:YYYY-MM-DD:type
    """
    prefix = settings.redis.agg_prefix
    return f"{prefix}:{day}:{tx_type}"

def parse_day_from_key(key: str) -> str:
    """
    Used by the Persistor to extract the date from a key name.
    """
    # Key shape: agg:2026-01-01:deposit
    parts = key.split(":")
    return parts[1]