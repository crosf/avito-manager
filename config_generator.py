import re
import sqlite3

CONFIG_PATH = "/opt/parser_avito/config.toml"


def generate_config():
    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()

    cur.execute("SELECT url FROM searches")
    urls = [row[0] for row in cur.fetchall()]

    conn.close()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = f.read()

    urls_block = "urls = [\n"

    for url in urls:
        urls_block += f'    "{url}",\n'

    urls_block += "]"

    config = re.sub(
        r"urls\s*=\s*\[(.*?)\]",
        urls_block,
        config,
        flags=re.S
    )

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(config)

    return len(urls)
