"""add notification channels and deliveries

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-19 12:15:50.292725

告警外部通知通道：

- `notification_channels`：通道配置（Webhook / 企业微信 / 钉钉 / 邮件），
  群机器人 Webhook 与 SMTP 口令等密钥字段加密落库（见 services/alert_notify_service.py）
- `notification_deliveries`：一条告警在某通道上的投递台账，
  `(alert_code, channel_id)` 唯一既是幂等键，也是排查发送失败的依据
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('notification_channels',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('channel_type', sa.String(length=32), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('config', sa.JSON(), nullable=True),
    sa.Column('min_severity', sa.String(length=16), nullable=True),
    sa.Column('alert_types', sa.JSON(), nullable=True),
    sa.Column('last_success_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.String(length=500), nullable=True),
    sa.Column('last_error_at', sa.DateTime(), nullable=True),
    sa.Column('remark', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notification_channels', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notification_channels_channel_type'), ['channel_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_channels_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_channels_enabled'), ['enabled'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_channels_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_channels_min_severity'), ['min_severity'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_channels_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('notification_deliveries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=True),
    sa.Column('alert_code', sa.String(length=64), nullable=False),
    sa.Column('channel_id', sa.Integer(), nullable=False),
    sa.Column('channel_type', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=True),
    sa.Column('error', sa.String(length=500), nullable=True),
    sa.Column('response_excerpt', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('alert_code', 'channel_id', name='uq_notification_delivery')
    )
    with op.batch_alter_table('notification_deliveries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notification_deliveries_alert_code'), ['alert_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_deliveries_channel_id'), ['channel_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_deliveries_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_deliveries_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_deliveries_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_deliveries_tenant_id'), ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('notification_deliveries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notification_deliveries_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_notification_deliveries_status'))
        batch_op.drop_index(batch_op.f('ix_notification_deliveries_id'))
        batch_op.drop_index(batch_op.f('ix_notification_deliveries_created_at'))
        batch_op.drop_index(batch_op.f('ix_notification_deliveries_channel_id'))
        batch_op.drop_index(batch_op.f('ix_notification_deliveries_alert_code'))

    op.drop_table('notification_deliveries')
    with op.batch_alter_table('notification_channels', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notification_channels_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_notification_channels_min_severity'))
        batch_op.drop_index(batch_op.f('ix_notification_channels_id'))
        batch_op.drop_index(batch_op.f('ix_notification_channels_enabled'))
        batch_op.drop_index(batch_op.f('ix_notification_channels_created_at'))
        batch_op.drop_index(batch_op.f('ix_notification_channels_channel_type'))

    op.drop_table('notification_channels')
    # ### end Alembic commands ###
