"""extend video_channels for gb28181 registration

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-19 10:00:00.000000

GB28181 接入复用 video_channels 台账：设备与通道都落在这一张表，
靠 gb_device_id（自身 20 位国标编码）与 parent_gb_id（空=设备节点）表达树形关系。

型号复用既有 device_model 列，不新增同义列，因此这里只补
gb_device_id / parent_gb_id / manufacturer / sip_register_at 四列。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    逐列/逐索引判断后再改，避免迁移中断后重跑（或开发库已由 create_all 补过列）
    时报 duplicate column 而卡住启动。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("video_channels")}
    indexes = {idx["name"] for idx in inspector.get_indexes("video_channels")}

    with op.batch_alter_table('video_channels', schema=None) as batch_op:
        if 'gb_device_id' not in columns:
            batch_op.add_column(sa.Column('gb_device_id', sa.String(length=32), nullable=True))
        if 'parent_gb_id' not in columns:
            batch_op.add_column(sa.Column('parent_gb_id', sa.String(length=32), nullable=True))
        if 'manufacturer' not in columns:
            batch_op.add_column(sa.Column('manufacturer', sa.String(length=128), nullable=True))
        if 'sip_register_at' not in columns:
            batch_op.add_column(sa.Column('sip_register_at', sa.DateTime(), nullable=True))
        if 'ix_video_channels_gb_device_id' not in indexes:
            batch_op.create_index(batch_op.f('ix_video_channels_gb_device_id'), ['gb_device_id'], unique=False)
        if 'ix_video_channels_parent_gb_id' not in indexes:
            batch_op.create_index(batch_op.f('ix_video_channels_parent_gb_id'), ['parent_gb_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('video_channels', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_video_channels_parent_gb_id'))
        batch_op.drop_index(batch_op.f('ix_video_channels_gb_device_id'))
        batch_op.drop_column('sip_register_at')
        batch_op.drop_column('manufacturer')
        batch_op.drop_column('parent_gb_id')
        batch_op.drop_column('gb_device_id')
