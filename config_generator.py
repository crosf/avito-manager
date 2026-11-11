import re
import sqlite3
from pathlib import Path
from settings import CONFIG_PATH, DB_PATH


def generate_config() -> int:
    config_file = Path(CONFIG_PATH)
    if not config_file.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден по пути: {CONFIG_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Выбираем только активные поиски (не на паузе)
    cur.execute("SELECT url FROM searches WHERE is_active = 1 ORDER BY id ASC")
    urls = [row[0] for row in cur.fetchall()]
    conn.close()

    with open(config_file, "r", encoding="utf-8") as f:
        config = f.read()

    urls_block = "urls = [\n"
    for url in urls:
        urls_block += f'    "{url}",\n'
    urls_block += "]"

    if re.search(r"urls\s*=\s*\[(.*?)\]", config, flags=re.S):
        config = re.sub(r"urls\s*=\s*\[(.*?)\]", urls_block, config, flags=re.S)
    else:
        config = f"{urls_block}\n\n{config}"

    with open(config_file, "w", encoding="utf-8") as f:
        f.write(config)

    return len(urls)


def get_current_interval() -> dict:
    """Возвращает текущую паузу между кругами (pause_general) в человекочитаемом виде."""
    config_file = Path(CONFIG_PATH)
    if not config_file.exists():
        return {"seconds": 3600, "minutes": 60, "human": "60 мин (1 час)"}

    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"^pause_general\s*=\s*(\d+)", content, flags=re.M)
    if not match:
        return {"seconds": 3600, "minutes": 60, "human": "60 мин (1 час)"}

    seconds = int(match.group(1))
    minutes = round(seconds / 60, 1)
    if minutes.is_integer():
        minutes = int(minutes)

    if seconds < 60:
        human = f"{seconds} сек"
    elif minutes < 60:
        human = f"{minutes} мин"
    elif minutes % 60 == 0:
        hours = minutes // 60
        human = f"{hours} ч ({minutes} мин)"
    else:
        human = f"{minutes} мин"

    return {"seconds": seconds, "minutes": minutes, "human": human}


def set_interval(seconds: int):
    """Обновляет pause_general в config.toml."""
    config_file = Path(CONFIG_PATH)
    if not config_file.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден по пути: {CONFIG_PATH}")

    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()

    if re.search(r"^pause_general\s*=\s*\d+", content, flags=re.M):
        content = re.sub(r"^pause_general\s*=\s*\d+", f"pause_general = {seconds}", content, flags=re.M)
    else:
        content = f"{content}\npause_general = {seconds}\n"

    with open(config_file, "w", encoding="utf-8") as f:
        f.write(content)


def sync_telegram_credentials(token: str, chat_ids: list[int]):
    """Синхронизирует токен Telegram и chat_id в config.toml парсера."""
    config_file = Path(CONFIG_PATH)
    if not config_file.exists() or not token:
        return

    with open(config_file, "r", encoding="utf-8") as f:
        config = f.read()

    config = re.sub(
        r'tg_token\s*=\s*["\'].*?["\']',
        f'tg_token = "{token}"',
        config
    )

    chats_str = ", ".join(str(c) for c in chat_ids)
    config = re.sub(
        r'tg_chat_id\s*=\s*\[.*?\]',
        f'tg_chat_id = [{chats_str}]',
        config
    )

    with open(config_file, "w", encoding="utf-8") as f:
        f.write(config)
