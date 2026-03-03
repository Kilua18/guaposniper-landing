import sys
from pathlib import Path

from loguru import logger


def setup_logger(level: str = "INFO", log_file: str = "logs/guapo-trader.log",
                 max_size: str = "10 MB", retention: str = "7 days"):
    """Configure loguru pour le bot."""
    logger.remove()

    # Console
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{message}</cyan>",
        colorize=True,
    )

    # Fichier
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path),
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
        rotation=max_size,
        retention=retention,
        compression="gz",
    )

    logger.info(f"Logger initialisé (level={level}, file={log_file})")
