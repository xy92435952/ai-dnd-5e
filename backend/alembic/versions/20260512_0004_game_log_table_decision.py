"""persist multiplayer table decision metadata on game logs

Revision ID: 20260512_0004_game_log_table_decision
Revises: 20260509_0003_game_log_visibility
Create Date: 2026-05-12 09:25:00

Store Multiplayer DM table coordination metadata with DM logs so reconnecting
clients can restore the same scheduling explanation shown during realtime play.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260512_0004_game_log_table_decision"
down_revision: Union[str, None] = "20260509_0003_game_log_visibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("game_logs") as batch:
        batch.add_column(sa.Column("table_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("table_decision", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("game_logs") as batch:
        batch.drop_column("table_decision")
        batch.drop_column("table_reason")
