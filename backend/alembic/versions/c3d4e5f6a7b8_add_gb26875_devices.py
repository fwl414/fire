"""add gb26875 device table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-19 09:00:00.000000

GB/T 26875 消防主机（用户信息传输装置）接入台账：接入服务按报文源地址
（6 字节 BCD，12 位十进制）查这张表做身份校验，未登记的地址一律否认。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'gb26875_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('device_code', sa.String(length=64), nullable=True),
        sa.Column('gb_address', sa.String(length=16), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column('password_cipher', sa.Text(), nullable=True),
        sa.Column('device_system_type', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('registered', sa.Boolean(), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('remote_ip', sa.String(length=64), nullable=True),
        sa.Column('remote_port', sa.Integer(), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gb_address', name='uq_gb26875_device_address'),
    )
    with op.batch_alter_table('gb26875_devices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_gb26875_devices_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_gb26875_devices_device_code'), ['device_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_gb26875_devices_enabled'), ['enabled'], unique=False)
        batch_op.create_index(batch_op.f('ix_gb26875_devices_gb_address'), ['gb_address'], unique=False)
        batch_op.create_index(batch_op.f('ix_gb26875_devices_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_gb26875_devices_last_heartbeat_at'), ['last_heartbeat_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_gb26875_devices_tenant_id'), ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('gb26875_devices', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gb26875_devices_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_gb26875_devices_last_heartbeat_at'))
        batch_op.drop_index(batch_op.f('ix_gb26875_devices_id'))
        batch_op.drop_index(batch_op.f('ix_gb26875_devices_gb_address'))
        batch_op.drop_index(batch_op.f('ix_gb26875_devices_enabled'))
        batch_op.drop_index(batch_op.f('ix_gb26875_devices_device_code'))
        batch_op.drop_index(batch_op.f('ix_gb26875_devices_created_at'))
    op.drop_table('gb26875_devices')
