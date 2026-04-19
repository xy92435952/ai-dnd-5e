"""baseline v0.8

Revision ID: 20260417_0001_baseline_v08
Revises:
Create Date: 2026-04-17 00:01:00

基线版本：标记 v0.8 已建表数据库的"起点"。

不做任何 DDL 操作。已经跑过旧版 migrate_*.py 或 init_db() 的实例，
应通过 `alembic stamp 20260417_0001_baseline_v08` 标记到此版本，
然后 `alembic upgrade head` 即可应用后续多人联机迁移。

全新数据库：alembic upgrade head 会从此版本开始顺序执行。
此基线本身是空操作，依赖后续迁移完成实际建表（或继续用 init_db() 兜底）。
"""
from typing import Sequence, Union


revision: str = "20260417_0001_baseline_v08"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 基线版本，无操作
    pass


def downgrade() -> None:
    pass
