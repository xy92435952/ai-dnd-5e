"""game log visibility for multiplayer private narration

Revision ID: 20260509_0003_game_log_visibility
Revises: 20260417_0002_multiplayer
Create Date: 2026-05-09 15:45:00

Persist per-log visibility so multiplayer private/group narration can be
filtered when a player refreshes or rejoins a session.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260509_0003_game_log_visibility"
down_revision: Union[str, None] = "20260417_0002_multiplayer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("game_logs") as batch:
        batch.add_column(sa.Column("visibility", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("game_logs") as batch:
        batch.drop_column("visibility")
