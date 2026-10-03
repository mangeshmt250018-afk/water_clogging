"""add report status and comments table

Revision ID: d4e5f6a7b8c9
Revises: 6c6170c427d4
Create Date: 2026-08-29 17:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = '6c6170c427d4'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Update 'reports' table with status and created_at
    if 'reports' in tables:
        report_columns = [col['name'] for col in inspector.get_columns('reports')]
        with op.batch_alter_table('reports', schema=None) as batch_op:
            if 'status' not in report_columns:
                batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=False, server_default='Submitted'))
            if 'created_at' not in report_columns:
                batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))

    # 2. Create 'comments' table if it does not exist
    if 'comments' not in tables:
        op.create_table(
            'comments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('report_id', sa.Integer(), sa.ForeignKey('reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('content', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'comments' in tables:
        op.drop_table('comments')

    if 'reports' in tables:
        report_columns = [col['name'] for col in inspector.get_columns('reports')]
        with op.batch_alter_table('reports', schema=None) as batch_op:
            if 'created_at' in report_columns:
                batch_op.drop_column('created_at')
            if 'status' in report_columns:
                batch_op.drop_column('status')
