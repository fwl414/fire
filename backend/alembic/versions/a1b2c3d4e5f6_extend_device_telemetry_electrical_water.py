"""extend device_telemetry with electrical and water metrics

Revision ID: a1b2c3d4e5f6
Revises: 7dbc18758246
Create Date: 2026-09-17 10:00:00.000000

补齐 current / voltage / pressure / remaining_current 4 个 nullable Float 列。
硬件本就在上报这 4 个指标（device_ingest_service.py 的 METRIC_ALIASES 已识别），
此前因 DeviceTelemetry 表无对应列而被丢进告警上下文不入时序表。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7dbc18758246'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('device_telemetry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('current', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('voltage', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('pressure', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('remaining_current', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('device_telemetry', schema=None) as batch_op:
        batch_op.drop_column('remaining_current')
        batch_op.drop_column('pressure')
        batch_op.drop_column('voltage')
        batch_op.drop_column('current')
