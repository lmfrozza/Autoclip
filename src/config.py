import os
import yaml
from loguru import logger

# --- Logger ---
os.makedirs("logs", exist_ok=True)

logger.add(
    "logs/app.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | {message}",
)

# --- Config ---
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _config = yaml.safe_load(_f)

streamers: list[str] = _config.get("streamers", [])
pipeline: dict = _config.get("pipeline", {})
watermark: dict = _config.get("watermark", {})
