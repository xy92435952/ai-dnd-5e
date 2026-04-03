"""
数据库迁移：添加 P0/P1 战斗特性所需的新列
- hit_dice_remaining: 短休可用生命骰数量
- class_resources:    职业资源追踪 (rage, second_wind, action_surge, etc.)
"""
import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "ai_trpg.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 检查列是否已存在
cur.execute("PRAGMA table_info(characters)")
cols = [row[1] for row in cur.fetchall()]

if "hit_dice_remaining" not in cols:
    cur.execute("ALTER TABLE characters ADD COLUMN hit_dice_remaining INTEGER")
    conn.commit()
    print("OK: Added hit_dice_remaining column")
else:
    print("SKIP: hit_dice_remaining already exists")

if "class_resources" not in cols:
    cur.execute("ALTER TABLE characters ADD COLUMN class_resources JSON DEFAULT '{}'")
    conn.commit()
    print("OK: Added class_resources column")
else:
    print("SKIP: class_resources already exists")

conn.close()
print("Migration complete.")
