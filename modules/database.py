import sqlite3
from typing import List, Tuple, Optional
from settings import DB_PATH


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()

    # Миграция: проверяем наличие новых колонок, если таблица была создана ранее
    cur.execute("PRAGMA table_info(searches)")
    columns = [col[1] for col in cur.fetchall()]

    if "title" not in columns:
        cur.execute("ALTER TABLE searches ADD COLUMN title TEXT")
    if "is_active" not in columns:
        cur.execute("ALTER TABLE searches ADD COLUMN is_active INTEGER DEFAULT 1")

    conn.commit()
    conn.close()


def get_searches(active_only: bool = False) -> List[Tuple]:
    conn = get_connection()
    cur = conn.cursor()
    if active_only:
        cur.execute("SELECT id, url, title, is_active FROM searches WHERE is_active = 1 ORDER BY id ASC")
    else:
        cur.execute("SELECT id, url, title, is_active FROM searches ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_search(search_id: int) -> Optional[Tuple]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, url, title, is_active FROM searches WHERE id = ?", (search_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_search(url: str, title: Optional[str] = None):
    conn = get_connection()
    cur = conn.cursor()
    url = url.strip()
    if not title:
        title = extract_default_title(url)

    cur.execute(
        "INSERT OR REPLACE INTO searches(url, title, is_active) VALUES(?, ?, 1)",
        (url, title)
    )
    conn.commit()
    conn.close()


def toggle_search_active(search_id: int) -> Optional[int]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_active FROM searches WHERE id = ?", (search_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    new_state = 0 if row[0] == 1 else 1
    cur.execute("UPDATE searches SET is_active = ? WHERE id = ?", (new_state, search_id))
    conn.commit()
    conn.close()
    return new_state


def delete_search(search_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM searches WHERE id=?", (search_id,))
    conn.commit()
    conn.close()


def count_searches(active_only: bool = False) -> int:
    conn = get_connection()
    cur = conn.cursor()
    if active_only:
        cur.execute("SELECT COUNT(*) FROM searches WHERE is_active = 1")
    else:
        cur.execute("SELECT COUNT(*) FROM searches")
    count = cur.fetchone()[0]
    conn.close()
    return count


def extract_default_title(url: str) -> str:
    """Извлекает читаемый заголовок из URL Авито"""
    try:
        if "q=" in url:
            query = url.split("q=")[-1].split("&")[0][:40]
            query = query.replace("+", " ").strip()
            if query:
                return query
        slug = url.split("?")[0].rstrip("/").split("/")[-1][:40]
        slug = slug.replace("_", " ").replace("-", " ").strip()
        return slug or "Поиск Авито"
    except Exception:
        return "Поиск Авито"
