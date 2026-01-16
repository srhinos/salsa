import sys

from loguru import logger

LOG_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

logger.remove()
logger.add(
    sys.stderr,
    format=LOG_FORMAT,
    level="DEBUG",
    colorize=True,
)

__all__ = ["logger"]
