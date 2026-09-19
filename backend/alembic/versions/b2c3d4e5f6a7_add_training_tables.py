"""add training plan / exam / record tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-17 11:00:00.000000

消防培训页面（/fire-training）原先三块数据全是写死的演示值：
培训计划、考试场次、培训档案。后端此前完全没有对应的表，
连一条真实记录都没有，因此这里一次补齐三张表。

考试场次的参考人数 / 平均分 / 及格率不落列，由 training_records 按
exam_id 聚合得出，避免统计值与档案不一致。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'training_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('plan_name', sa.String(length=128), nullable=False),
        sa.Column('plan_type', sa.String(length=32), nullable=True),
        sa.Column('target', sa.String(length=128), nullable=True),
        sa.Column('trainer', sa.String(length=64), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('person_count', sa.Integer(), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('training_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_training_plans_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_plans_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_plans_plan_type'), ['plan_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_plans_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_plans_tenant_id'), ['tenant_id'], unique=False)

    op.create_table(
        'training_exams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('question_count', sa.Integer(), nullable=True),
        sa.Column('pass_score', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('training_exams', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_training_exams_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_exams_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_exams_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_exams_tenant_id'), ['tenant_id'], unique=False)

    op.create_table(
        'training_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('trainee_name', sa.String(length=64), nullable=False),
        sa.Column('department', sa.String(length=64), nullable=True),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('course_name', sa.String(length=128), nullable=True),
        sa.Column('train_date', sa.Date(), nullable=True),
        sa.Column('study_hours', sa.Float(), nullable=True),
        sa.Column('exam_id', sa.Integer(), nullable=True),
        sa.Column('exam_score', sa.Float(), nullable=True),
        sa.Column('cert_no', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['training_plans.id'], ),
        sa.ForeignKeyConstraint(['exam_id'], ['training_exams.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('training_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_training_records_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_records_department'), ['department'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_records_exam_id'), ['exam_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_records_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_records_plan_id'), ['plan_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_records_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_records_train_date'), ['train_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_records_trainee_name'), ['trainee_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('training_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_records_trainee_name'))
        batch_op.drop_index(batch_op.f('ix_training_records_train_date'))
        batch_op.drop_index(batch_op.f('ix_training_records_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_training_records_plan_id'))
        batch_op.drop_index(batch_op.f('ix_training_records_id'))
        batch_op.drop_index(batch_op.f('ix_training_records_exam_id'))
        batch_op.drop_index(batch_op.f('ix_training_records_department'))
        batch_op.drop_index(batch_op.f('ix_training_records_created_at'))
    op.drop_table('training_records')

    with op.batch_alter_table('training_exams', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_exams_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_training_exams_status'))
        batch_op.drop_index(batch_op.f('ix_training_exams_id'))
        batch_op.drop_index(batch_op.f('ix_training_exams_created_at'))
    op.drop_table('training_exams')

    with op.batch_alter_table('training_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_plans_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_training_plans_status'))
        batch_op.drop_index(batch_op.f('ix_training_plans_plan_type'))
        batch_op.drop_index(batch_op.f('ix_training_plans_id'))
        batch_op.drop_index(batch_op.f('ix_training_plans_created_at'))
    op.drop_table('training_plans')
