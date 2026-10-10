"""结构化日志配置。"""
import logging
import sys

from app.core import config


def setup_logging() -> None:
    """配置根日志器：级别取自 LOG_LEVEL（默认 INFO），统一格式输出到 stdout。"""
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )