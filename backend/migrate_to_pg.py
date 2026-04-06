"""
SQLite → PostgreSQL 数据迁移脚本
=================================
将 ai_trpg.db 中的所有数据迁移到 PostgreSQL。

使用方式：
  1. 确保 PostgreSQL 已安装并创建了数据库
  2. 在 .env 中设置 DATABASE_URL 为 PostgreSQL 连接串
  3. 运行: python migrate_to_pg.py

注意：
  - 此脚本会先在 PostgreSQL 中创建表，然后逐表迁移数据
  - 如果 PostgreSQL 中已有数据，会跳过该表
  - SQLite 数据库不会被修改
"""

import sqlite3
import json
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def migrate():
    from config import settings

    if "sqlite" in settings.database_url:
        print("ERROR: DATABASE_URL 仍然是 SQLite，请在 .env 中设置 PostgreSQL 连接串")
        print("  例如: DATABASE_URL=postgresql+asyncpg://ai_trpg:password@localhost:5432/ai_trpg")
        return

    # 连接 SQLite 源数据库
    sqlite_path = os.path.join(os.path.dirname(__file__), "ai_trpg.db")
    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite 数据库不存在: {sqlite_path}")
        return

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # 初始化 PostgreSQL（创建表）
    from database import engine, Base, init_db
    # 导入所有模型确保 Base.metadata 包含所有表
    from models import Module, Character, Session, GameLog, CombatState
    from models.user import User

    print("═══════════════════════════════════════")
    print("  SQLite → PostgreSQL 数据迁移")
    print("═══════════════════════════════════════")
    print(f"  源: {sqlite_path}")
    print(f"  目标: {settings.database_url.split('@')[1] if '@' in settings.database_url else settings.database_url}")
    print()

    # 创建 PostgreSQL 表
    print("[1/7] 创建 PostgreSQL 表...")
    await init_db()
    print("  表结构已创建")

    # 迁移顺序（按外键依赖）
    tables = [
        ("users", ["id", "username", "password_hash", "display_name", "created_at"]),
        ("modules", ["id", "user_id", "name", "file_path", "file_type", "parsed_content",
                      "level_min", "level_max", "recommended_party_size",
                      "parse_status", "parse_error", "created_at"]),
        ("sessions", ["id", "user_id", "module_id", "player_character_id",
                       "current_scene", "session_history", "game_state", "combat_active",
                       "campaign_state", "dify_conversation_id", "save_name",
                       "created_at", "updated_at"]),
        ("characters", None),  # 太多列，动态获取
        ("combat_states", ["id", "session_id", "grid_data", "entity_positions",
                           "turn_order", "current_turn_index", "round_number",
                           "combat_log", "turn_states", "created_at", "updated_at"]),
        ("game_logs", ["id", "session_id", "role", "content", "log_type",
                       "dice_result", "created_at"]),
    ]

    # JSON 类型的列（需要特殊处理）
    json_columns = {
        "parsed_content", "game_state", "campaign_state", "ability_scores",
        "derived", "spell_slots", "known_spells", "prepared_spells", "cantrips",
        "proficient_skills", "proficient_saves", "languages", "tool_proficiencies",
        "feats", "equipment", "conditions", "condition_durations", "death_saves",
        "class_resources", "multiclass_info", "grid_data", "entity_positions",
        "turn_order", "combat_log", "turn_states", "dice_result",
    }

    from sqlalchemy.ext.asyncio import AsyncSession as PgSession
    from database import AsyncSessionLocal
    from sqlalchemy import text

    for i, (table_name, columns) in enumerate(tables):
        print(f"\n[{i+2}/7] 迁移 {table_name}...")

        # 检查 SQLite 中是否有此表
        cursor.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone()[0] == 0:
            print(f"  跳过（SQLite 中无此表）")
            continue

        # 获取列名
        if columns is None:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]

        # 检查 SQLite 中实际存在的列
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_cols = {row[1] for row in cursor.fetchall()}
        valid_columns = [c for c in columns if c in existing_cols]

        # 读取 SQLite 数据
        cursor.execute(f"SELECT {','.join(valid_columns)} FROM {table_name}")
        rows = cursor.fetchall()
        print(f"  SQLite 中有 {len(rows)} 行")

        if len(rows) == 0:
            print(f"  跳过（无数据）")
            continue

        # 检查 PostgreSQL 中是否已有数据
        async with AsyncSessionLocal() as pg_session:
            result = await pg_session.execute(text(f"SELECT count(*) FROM {table_name}"))
            pg_count = result.scalar()
            if pg_count > 0:
                print(f"  跳过（PostgreSQL 中已有 {pg_count} 行）")
                continue

        # 插入到 PostgreSQL
        migrated = 0
        async with AsyncSessionLocal() as pg_session:
            for row in rows:
                values = {}
                for j, col in enumerate(valid_columns):
                    val = row[j]
                    # JSON 列：SQLite 存的是字符串，PostgreSQL 需要 dict/list
                    if col in json_columns and isinstance(val, str):
                        try:
                            val = json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    # Boolean 列
                    if col == "combat_active" and isinstance(val, int):
                        val = bool(val)
                    if col == "is_player" and isinstance(val, int):
                        val = bool(val)
                    values[col] = val

                cols_str = ", ".join(values.keys())
                params_str = ", ".join(f":{k}" for k in values.keys())
                stmt = text(f"INSERT INTO {table_name} ({cols_str}) VALUES ({params_str})")
                try:
                    await pg_session.execute(stmt, values)
                    migrated += 1
                except Exception as e:
                    print(f"  警告: 行 {migrated+1} 插入失败: {e}")

            await pg_session.commit()
        print(f"  已迁移 {migrated}/{len(rows)} 行")

    sqlite_conn.close()

    # 验证
    print("\n[验证] 对比数据行数...")
    async with AsyncSessionLocal() as pg_session:
        for table_name, _ in tables:
            try:
                result = await pg_session.execute(text(f"SELECT count(*) FROM {table_name}"))
                pg_count = result.scalar()
                print(f"  {table_name}: {pg_count} 行")
            except Exception:
                print(f"  {table_name}: 表不存在")

    print("\n═══════════════════════════════════════")
    print("  迁移完成！")
    print("═══════════════════════════════════════")


if __name__ == "__main__":
    asyncio.run(migrate())
