"""multiplayer (v0.9)

Revision ID: 20260417_0002_multiplayer
Revises: 20260417_0001_baseline_v08
Create Date: 2026-04-17 00:02:00

引入多人联机支持：
1. characters 表新增 user_id（FK -> users.id）
2. sessions 表新增 is_multiplayer / room_code / host_user_id / max_players
3. 新建 session_members 表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0002_multiplayer"
down_revision: Union[str, None] = "20260417_0001_baseline_v08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. characters.user_id ──────────────────────────────
    with op.batch_alter_table("characters") as batch:
        batch.add_column(sa.Column("user_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_characters_user_id",
            "users",
            ["user_id"], ["id"],
        )
        batch.create_index("ix_characters_user_id", ["user_id"])

    # ── 2. sessions 多人字段 ───────────────────────────────
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column(
            "is_multiplayer", sa.Boolean(),
            server_default=sa.false(), nullable=False,
        ))
        batch.add_column(sa.Column("room_code", sa.String(length=6), nullable=True))
        batch.add_column(sa.Column("host_user_id", sa.String(), nullable=True))
        batch.add_column(sa.Column(
            "max_players", sa.Integer(),
            server_default="4", nullable=False,
        ))
        batch.create_unique_constraint("uq_sessions_room_code", ["room_code"])
        batch.create_index("ix_sessions_room_code", ["room_code"])
        batch.create_foreign_key(
            "fk_sessions_host_user_id",
            "users",
            ["host_user_id"], ["id"],
        )

    # ── 3. session_members 表 ─────────────────────────────
    op.create_table(
        "session_members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("character_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(length=20), server_default="player"),
        sa.Column("joined_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"]),
        sa.UniqueConstraint("session_id", "user_id", name="uq_session_user"),
    )
    op.create_index("ix_session_members_session_id", "session_members", ["session_id"])
    op.create_index("ix_session_members_user_id", "session_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_session_members_user_id", table_name="session_members")
    op.drop_index("ix_session_members_session_id", table_name="session_members")
    op.drop_table("session_members")

    with op.batch_alter_table("sessions") as batch:
        batch.drop_constraint("fk_sessions_host_user_id", type_="foreignkey")
        batch.drop_index("ix_sessions_room_code")
        batch.drop_constraint("uq_sessions_room_code", type_="unique")
        batch.drop_column("max_players")
        batch.drop_column("host_user_id")
        batch.drop_column("room_code")
        batch.drop_column("is_multiplayer")

    with op.batch_alter_table("characters") as batch:
        batch.drop_index("ix_characters_user_id")
        batch.drop_constraint("fk_characters_user_id", type_="foreignkey")
        batch.drop_column("user_id")
