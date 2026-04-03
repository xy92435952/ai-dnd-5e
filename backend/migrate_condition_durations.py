import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "ai_trpg.db")
conn = sqlite3.connect(db_path)
cur  = conn.cursor()

cur.execute("PRAGMA table_info(characters)")
cols = [row[1] for row in cur.fetchall()]

if "condition_durations" not in cols:
    cur.execute("ALTER TABLE characters ADD COLUMN condition_durations JSON")
    conn.commit()
    print("OK: Added condition_durations column")
else:
    print("SKIP: condition_durations already exists")

conn.close()
