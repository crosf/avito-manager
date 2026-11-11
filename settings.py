import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Загружаем переменные из .env файла
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Поддержка одного или нескольких ID администраторов через запятую
_admin_ids_raw = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "")).strip()
ADMIN_IDS = set()
for item in _admin_ids_raw.split(","):
    item = item.strip()
    if item.isdigit():
        ADMIN_IDS.add(int(item))

if not BOT_TOKEN:
    logger.warning("Внимание: BOT_TOKEN не задан в .env файле!")
if not ADMIN_IDS:
    logger.warning("Внимание: ADMIN_IDS не заданы в .env файле! Доступ к боту будет заблокирован.")

CONFIG_PATH = os.getenv("CONFIG_PATH", "/opt/parser_avito/config.toml")
PARSER_PATH = os.getenv("PARSER_PATH", "/opt/parser_avito")
PARSER_CONTAINER_NAME = os.getenv("PARSER_CONTAINER_NAME", "avito")
DB_PATH = os.getenv("DB_PATH", "searches.db")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
