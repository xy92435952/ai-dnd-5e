"""清理测试阶段产生的临时数据。

上线前运行一次，删除：
- 测试用户（username 以 mp_ / test_ 开头）
- 测试模组（name 以 __test_module 开头）
- 这些用户创建的会话、角色、战斗状态、日志、房间成员

保留 username='test' / '123' 等手动创建的真人账号。

用法:
    cd backend
    python cleanup_test_data.py --dry-run   # 预览
    python cleanup_test_data.py --apply     # 实际删除
"""
import argparse
import sys
from sqlalchemy import create_engine, text

from config import settings


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只预览不删除")
    parser.add_argument("--apply", action="store_true", help="实际执行删除")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("必须指定 --dry-run 或 --apply")

    # 把 async URL 转同步 URL
    url = settings.database_url
    if url.startswith("sqlite+aiosqlite"):
        url = url.replace("sqlite+aiosqlite", "sqlite", 1)
    elif url.startswith("postgresql+asyncpg"):
        url = url.replace("postgresql+asyncpg", "postgresql+psycopg", 1)

    engine = create_engine(url)

    with engine.connect() as conn:
        # 1. 找测试用户
        user_rows = conn.execute(text("""
            SELECT id, username FROM users
            WHERE username LIKE 'mp_%'
               OR username LIKE 'test_%'
               OR username LIKE 'mp_extra_%'
               OR username LIKE 'mp_intruder_%'
               OR username LIKE 'mp_host_%'
               OR username LIKE 'mp_p_%'
        """)).all()

        print(f"[users] {len(user_rows)} test users found:")
        for u in user_rows:
            print(f"  - {u[0][:8]} {u[1]}")

        # 2. 找测试模组
        mod_rows = conn.execute(text("""
            SELECT id, name FROM modules
            WHERE name LIKE '__test_module%'
        """)).all()
        print(f"\n[modules] {len(mod_rows)} test modules:")
        for m in mod_rows:
            print(f"  - {m[0][:8]} {m[1][:40]}")

        user_ids = [u[0] for u in user_rows]
        mod_ids = [m[0] for m in mod_rows]

        if not user_ids and not mod_ids:
            print("\n✓ 没有需要清理的测试数据")
            return

        # 3. 找将被级联清理的数据量（给用户看清楚）
        session_count = 0
        if user_ids:
            placeholders = ",".join([f"'{uid}'" for uid in user_ids])
            session_count = conn.execute(text(
                f"SELECT COUNT(*) FROM sessions WHERE user_id IN ({placeholders})"
            )).scalar()

        print(f"\n[sessions] {session_count} sessions will be deleted (cascade)")

        if args.dry_run:
            print("\n---DRY RUN---  Run with --apply to actually delete.")
            return

        # 4. 实际删除（按外键依赖顺序）
        print("\nDeleting...")
        if user_ids:
            placeholders = ",".join([f"'{uid}'" for uid in user_ids])

            # 找所有这些用户的 session id
            sess_ids = [r[0] for r in conn.execute(text(
                f"SELECT id FROM sessions WHERE user_id IN ({placeholders})"
            )).all()]

            if sess_ids:
                sess_place = ",".join([f"'{s}'" for s in sess_ids])
                # 按依赖顺序清
                conn.execute(text(f"DELETE FROM session_members WHERE session_id IN ({sess_place})"))
                conn.execute(text(f"DELETE FROM game_logs WHERE session_id IN ({sess_place})"))
                conn.execute(text(f"DELETE FROM combat_states WHERE session_id IN ({sess_place})"))
                conn.execute(text(f"UPDATE characters SET session_id = NULL WHERE session_id IN ({sess_place})"))
                conn.execute(text(f"DELETE FROM sessions WHERE id IN ({sess_place})"))

            # 清用户拥有的角色
            conn.execute(text(f"DELETE FROM characters WHERE user_id IN ({placeholders})"))
            # 清用户拥有的模组（但不级联清真实用户上传的同名模组）
            conn.execute(text(f"DELETE FROM modules WHERE user_id IN ({placeholders})"))
            # 清用户本身
            conn.execute(text(f"DELETE FROM users WHERE id IN ({placeholders})"))

        if mod_ids:
            placeholders = ",".join([f"'{mid}'" for mid in mod_ids])
            conn.execute(text(f"DELETE FROM modules WHERE id IN ({placeholders})"))

        conn.commit()
        print("✓ 清理完成")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
