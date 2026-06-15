import sqlite3

conn = sqlite3.connect("searches.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS searches(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL
)
""")

conn.commit()
conn.close()

print("DB created")
