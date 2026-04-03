"""
用户系统迁移：
1. 创建 users 表
2. 为 modules / sessions 添加 user_id 列
3. 创建测试账号 test/123456
"""
import sqlite3
import bcrypt
import uuid

DB_PATH = "ai_trpg.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 创建 users 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(200) NOT NULL,
            display_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  users 表已创建")

    # 2. 为 modules 添加 user_id
    cols = {row[1] for row in cursor.execute("PRAGMA table_info(modules)").fetchall()}
    if "user_id" not in cols:
        cursor.execute("ALTER TABLE modules ADD COLUMN user_id VARCHAR REFERENCES users(id)")
        print("  modules.user_id 已添加")
    else:
        print("  modules.user_id 已存在")

    # 3. 为 sessions 添加 user_id
    cols = {row[1] for row in cursor.execute("PRAGMA table_info(sessions)").fetchall()}
    if "user_id" not in cols:
        cursor.execute("ALTER TABLE sessions ADD COLUMN user_id VARCHAR REFERENCES users(id)")
        print("  sessions.user_id 已添加")
    else:
        print("  sessions.user_id 已存在")

    # 4. 创建测试账号
    existing = cursor.execute("SELECT id FROM users WHERE username = 'test'").fetchone()
    if existing:
        print("  测试账号 test 已存在")
    else:
        test_id = str(uuid.uuid4())
        pw_hash = bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT INTO users (id, username, password_hash, display_name) VALUES (?, ?, ?, ?)",
            (test_id, "test", pw_hash, "测试玩家")
        )
        # 将现有的无主数据关联到测试账号
        cursor.execute("UPDATE modules SET user_id = ? WHERE user_id IS NULL", (test_id,))
        cursor.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (test_id,))
        print(f"  测试账号已创建: test / 123456 (id={test_id[:12]}...)")

    conn.commit()
    conn.close()
    print("用户系统迁移完成。")

if __name__ == "__main__":
    migrate()
