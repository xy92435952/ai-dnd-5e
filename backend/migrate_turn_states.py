"""
迁移脚本：给 combat_states 表新增 turn_states 列
"""
import sqlite3, pathlib

DB = pathlib.Path(__file__).parent / "ai_trpg.db"

with sqlite3.connect(DB) as conn:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(combat_states)")
    cols = [row[1] for row in cur.fetchall()]
    if "turn_states" not in cols:
        cur.execute("ALTER TABLE combat_states ADD COLUMN turn_states TEXT")
        conn.commit()
        print("✅ 已添加 turn_states 列")
    else:
        print("ℹ️  turn_states 列已存在，跳过")
