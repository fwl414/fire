"""add floors.source_upload_id missing from baseline

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-19 09:30:00.000000

`database.Floor.source_upload_id` 在模型里一直存在，但基线迁移从未建这一列：
开发环境靠 `init_db()` 里的 `_migrate_sqlite_columns()` 自动补列，所以本地无感知；
生产分支不执行补列，全新 PostgreSQL 库会直接缺列 —— SQLAlchemy 查询 floors 时会
带出该列并报 "column floors.source_upload_id does not exist"，即首次部署即不可用。
这里补上，保证「结构唯一来源 Alembic」这条约定成立。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    这一列在开发库里可能已由 `init_db()` 的 `_migrate_sqlite_columns()` 补过，
    因此按「列/索引分别判断」的方式幂等执行，避免存量库升级时报 duplicate column。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("floors")}
    indexes = {idx["name"] for idx in inspector.get_indexes("floors")}

    with op.batch_alter_table('floors', schema=None) as batch_op:
        if 'source_upload_id' not in columns:
            batch_op.add_column(sa.Column('source_upload_id', sa.Integer(), nullable=True))
        if 'ix_floors_source_upload_id' not in indexes:
            batch_op.create_index(batch_op.f('ix_floors_source_upload_id'), ['source_upload_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('floors', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_floors_source_upload_id'))
        batch_op.drop_column('source_upload_id')
