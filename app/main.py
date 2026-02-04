import os
import logging
import logging.config

from fastapi import FastAPI

from app.core.lifespan import lifespan
from app.api.stats import router as stats_router
from app.api.health import router as health_router

LOG_DIR = "/logs"


def setup_logging() -> None:
    # Make sure log directory exists (important for Docker)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Get level from env (upper for safety)
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": os.path.join(LOG_DIR, "app.log"),
                    "formatter": "default",
                },
            },
            "root": {
                "level": log_level,  # Now dynamic from env
                "handlers": ["default", "file"],
            },
            "loggers": {
                "app.services.importer": {
                    "level": log_level if log_level == 'DEBUG' else "INFO",
                    "handlers": ["file", "default"],  # Add console for visibility
                    "propagate": False,
                },
                "app.services.aggregator": {
                    "level": log_level,
                    "handlers": ["file"],
                    "propagate": False,
                },
                "app.services.persistor": {
                    "level": log_level,
                    "handlers": ["file", "default"],  # Ensure dump messages hit console
                    "propagate": False,
                },
            },

        }
    )


setup_logging()

app = FastAPI(lifespan=lifespan)

app.include_router(stats_router)
app.include_router(health_router)

