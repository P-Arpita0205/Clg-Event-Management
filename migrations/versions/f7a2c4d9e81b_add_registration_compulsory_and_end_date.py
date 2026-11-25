"""Add registration_compulsory and ensure end_date on events

Revision ID: f7a2c4d9e81b
Revises: e4f8a91c2b3d
Create Date: 2026-11-26 01:38:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7a2c4d9e81b"
down_revision = "e4f8a91c2b3d"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing_columns = {col["name"] for col in inspector.get_columns("events")}

    with op.batch_alter_table("events", schema=None) as batch_op:
        if "end_date" not in existing_columns:
            batch_op.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        if "registration_compulsory" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "registration_compulsory",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )


def downgrade():
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_column("registration_compulsory")
