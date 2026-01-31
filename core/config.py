from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
import os
import re
import yaml

from pydantic import BaseModel


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env(value: str) -> str:
    def replacer(match: re.Match) -> str:
        var = match.group(1)
        return os.environ.get(var, "")
    return _ENV_PATTERN.sub(replacer, value)


def _expand_tree(obj):
    if isinstance(obj, dict):
        return {k: _expand_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_tree(v) for v in obj]
    if isinstance(obj, str):
        return _expand_env(obj)
    return obj


class RedisSettings(BaseModel):
    host: str
    port: int
    username: str
    password: str
    decode_responses: bool = True


class AppSettings(BaseModel):
    redis: RedisSettings
    csv_path: Path
    batch_size: int = 10


def load_settings() -> AppSettings:
    base_dir = Path(__file__).parent
    config_path = base_dir / "settings.yaml"

    if not config_path.exists():
        raise RuntimeError(
            f"Missing settings file: {config_path}. "
            "Create it from settings.example.yaml"
        )

    with config_path.open("r") as f:
        raw = yaml.safe_load(f)

    raw = _expand_tree(raw)

    return AppSettings(
        redis=RedisSettings(**raw["redis"]),
        csv_path=Path(raw["app"]["csv_path"]),
        batch_size=raw["app"]["batch_size"],
    )


settings = load_settings()
