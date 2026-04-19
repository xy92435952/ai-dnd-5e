# Alembic 数据库迁移

本项目从 v0.9 起引入 Alembic 管理数据库 schema 演进，取代此前手写的 `migrate_*.py` 脚本。

## 关系约定

- **基线版本（baseline）**：`20260417_0001_baseline_v08.py`
  - 不做任何 DDL 操作，仅作为 v0.8 已建表数据库的"起点"标记。
  - 任何已经跑过旧版 `migrate_*.py` 或 `init_db()` 的实例，都视为处于此基线之上。
- **多人联机迁移**：`20260417_0002_multiplayer.py`
  - 新增 `session_members` 表
  - `sessions` 加 `room_code` / `is_multiplayer` / `host_user_id` / `max_players`
  - `characters` 加 `user_id`

## 常用命令

> 在 `backend/` 目录下运行；环境变量按 `.env` 自动读取。

```bash
# 查看当前 DB 版本
alembic current

# 升级到最新
alembic upgrade head

# 升级一格
alembic upgrade +1

# 回滚一格
alembic downgrade -1

# 回滚到特定版本
alembic downgrade <revision>

# 查看历史
alembic history --verbose

# 标记当前 DB 为某个版本（不执行任何 DDL）
alembic stamp <revision>
```

## 首次接入流程

### 已有 v0.8 数据库（已跑过旧迁移脚本或 init_db）

```bash
cd backend
pip install -r requirements.txt        # 装上 alembic
alembic stamp 20260417_0001_baseline_v08   # 标记为基线
alembic upgrade head                       # 升级到最新（执行多人联机迁移）
```

### 全新数据库

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head    # baseline 是空操作，直接跑到 head
```

> 注意：`init_db()`（`Base.metadata.create_all`）会创建所有当前模型对应的表。
> 推荐：**新部署不再依赖 init_db()，统一用 alembic upgrade head**。

## 新增迁移

```bash
# 自动检测模型变更生成迁移（推荐）
alembic revision --autogenerate -m "<message>"

# 手写迁移
alembic revision -m "<message>"
```

生成后 **务必检查迁移文件内容**，autogenerate 不能自动识别所有变更（如类型变更、约束）。
