from loguru import logger
import os

os.makedirs("logs", exist_ok=True)

logger.add("logs/scraper.log", rotation="1 MB", retention="7 days")

def get_logger():
    return logger
