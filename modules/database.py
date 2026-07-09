import sqlite3

DB_PATH = "searches.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def get_searches():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, url FROM searches"
    )

    rows = cur.fetchall()

    conn.close()

    return rows


def add_search(url):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO searches(url) VALUES(?)",
        (url,)
    )

    conn.commit()
    conn.close()


def delete_search(search_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM searches WHERE id=?",
        (search_id,)
    )

    conn.commit()
    conn.close()


def count_searches():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM searches"
    )

    count = cur.fetchone()[0]

    conn.close()

    return count
