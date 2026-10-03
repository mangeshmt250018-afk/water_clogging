"""initial migration

Revision ID: 6c6170c427d4
Revises: 
Create Date: 2026-08-29 12:29:02.600550

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6c6170c427d4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Handle 'users' table
    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=20), nullable=False),
            sa.Column('email', sa.String(length=100), nullable=False, unique=True),
            sa.Column('password', sa.String(), nullable=False),
            sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('last_verification_sent', sa.DateTime(), nullable=True)
        )
    else:
        user_columns = [col['name'] for col in inspector.get_columns('users')]
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'last_verification_sent' not in user_columns:
                batch_op.add_column(sa.Column('last_verification_sent', sa.DateTime(), nullable=True))
            batch_op.alter_column('password',
                   existing_type=sa.String(),
                   nullable=False)

    # 2. Handle 'reports' / 'report' table
    if 'reports' not in tables and 'report' in tables:
        op.rename_table('report', 'reports')
        with op.batch_alter_table('reports', schema=None) as batch_op:
            batch_op.alter_column('author_id',
                   existing_type=sa.Integer(),
                   nullable=False)
            batch_op.alter_column('latitude',
                   existing_type=sa.Float(),
                   nullable=False)
            batch_op.alter_column('longitude',
                   existing_type=sa.Float(),
                   nullable=False)
    elif 'reports' not in tables and 'report' not in tables:
        op.create_table(
            'reports',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('cause', sa.String(), nullable=False),
            sa.Column('latitude', sa.Float(), nullable=False),
            sa.Column('longitude', sa.Float(), nullable=False),
            sa.Column('image_path', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True)
        )
    elif 'reports' in tables:
        with op.batch_alter_table('reports', schema=None) as batch_op:
            batch_op.alter_column('author_id',
                   existing_type=sa.Integer(),
                   nullable=False)
            batch_op.alter_column('latitude',
                   existing_type=sa.Float(),
                   nullable=False)
            batch_op.alter_column('longitude',
                   existing_type=sa.Float(),
                   nullable=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'users' in tables:
        user_columns = [col['name'] for col in inspector.get_columns('users')]
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.alter_column('password',
                   existing_type=sa.String(),
                   nullable=True)
            if 'last_verification_sent' in user_columns:
                batch_op.drop_column('last_verification_sent')

    if 'reports' in tables:
        with op.batch_alter_table('reports', schema=None) as batch_op:
            batch_op.alter_column('author_id',
                   existing_type=sa.Integer(),
                   nullable=True)
            batch_op.alter_column('latitude',
                   existing_type=sa.Float(),
                   nullable=True)
            batch_op.alter_column('longitude',
                   existing_type=sa.Float(),
                   nullable=True)
        op.rename_table('reports', 'report')
