"""
Phase 12 数据库迁移：添加 fighting_style / languages / tool_proficiencies / feats 列
"""
import sqlite3

DB_PATH = "ai_trpg.db"

MIGRATIONS = [
    ("fighting_style",     "VARCHAR(50)"),
    ("languages",          "TEXT DEFAULT '[]'"),
    ("tool_proficiencies", "TEXT DEFAULT '[]'"),
    ("feats",              "TEXT DEFAULT '[]'"),
]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取现有列名
    cursor.execute("PRAGMA table_info(characters)")
    existing = {row[1] for row in cursor.fetchall()}

    for col_name, col_type in MIGRATIONS:
        if col_name not in existing:
            sql = f"ALTER TABLE characters ADD COLUMN {col_name} {col_type}"
            print(f"  Adding column: {col_name} ({col_type})")
            cursor.execute(sql)
        else:
            print(f"  Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Phase 12 migration complete.")


if __name__ == "__main__":
    migrate()
