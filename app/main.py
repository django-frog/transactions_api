import logging
import logging.config

from fastapi import FastAPI

from app.core.lifespan import lifespan


def setup_logging() -> None:
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
                    "filename": "/logs/app.log",
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
                    "handlers": ["default", "file"],
                    "propagate": False,
                },
                "app.services.aggregator": {
                    "level": "INFO",
                    "handlers": ["default", "file"],
                    "propagate": False,
                },
                "app.services.persistor": {
                    "level": "INFO",
                    "handlers": ["default", "file"],
                    "propagate": False,
                },
            },

        }
    )


setup_logging()

app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}
