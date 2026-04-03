"""
迁移脚本：为 sessions 表添加 dify_conversation_id 列
运行方式：cd backend && python migrate_dify_conversation_id.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ai_trpg.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(sessions)")
    columns = [row[1] for row in cur.fetchall()]

    if "dify_conversation_id" not in columns:
        cur.execute("ALTER TABLE sessions ADD COLUMN dify_conversation_id TEXT")
        conn.commit()
        print("OK: dify_conversation_id 列已添加到 sessions 表")
    else:
        print("SKIP: dify_conversation_id 列已存在，无需迁移")

    conn.close()


if __name__ == "__main__":
    migrate()
