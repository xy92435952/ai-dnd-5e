import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "ai_trpg.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 检查列是否已存在
cur.execute("PRAGMA table_info(characters)")
cols = [row[1] for row in cur.fetchall()]
if "multiclass_info" not in cols:
    cur.execute("ALTER TABLE characters ADD COLUMN multiclass_info JSON")
    conn.commit()
    print("OK: Added multiclass_info column")
else:
    print("SKIP: multiclass_info already exists")

conn.close()
