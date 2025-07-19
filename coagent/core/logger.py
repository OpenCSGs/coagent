import sys

from loguru import logger


def init_logger(level: str = "INFO"):
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{level: <8}</level> | <level>{message}</level>",
    )
    logger.level("DEBUG", color="<fg 128,128,128>")


# For backwards compatibility.
set_stderr_logger = init_logger
