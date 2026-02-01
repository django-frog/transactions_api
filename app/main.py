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
                "level": "INFO",
                "handlers": ["default", "file"],
            },
            "loggers": {
                "app.services.importer": {
                    "level": "DEBUG",
                    "handlers": ["file"],
                    "propagate": False,
                },
                "app.services.aggregator": {
                    "level": "INFO",
                    "handlers": ["file"],
                    "propagate": False,
                },
                "app.services.persistor": {
                    "level": "INFO",
                    "handlers": ["file"],
                    "propagate": False,
                },
            },

        }
    )


setup_logging()

app = FastAPI(lifespan=lifespan)

app.include_router(stats_router)
app.include_router(health_router)

