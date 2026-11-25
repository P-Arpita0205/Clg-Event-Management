"""Add volunteer QR token and nullable attendance registration

Revision ID: e4f8a91c2b3d
Revises: 3d033d72dd65
Create Date: 2026-11-26 01:07:00.000000

"""
import secrets

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e4f8a91c2b3d"
down_revision = "3d033d72dd65"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("volunteer_applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("qr_token", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id FROM volunteer_applications WHERE qr_token IS NULL")
    ).fetchall()
    for row in rows:
        connection.execute(
            sa.text("UPDATE volunteer_applications SET qr_token = :token WHERE id = :id"),
            {"token": secrets.token_urlsafe(32), "id": row.id},
        )

    with op.batch_alter_table("volunteer_applications", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_volunteer_application_qr_token", ["qr_token"])

    with op.batch_alter_table("attendance", schema=None) as batch_op:
        batch_op.alter_column("registration_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("volunteer_application_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_attendance_volunteer_application_id",
            "volunteer_applications",
            ["volunteer_application_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("attendance", schema=None) as batch_op:
        batch_op.drop_constraint("fk_attendance_volunteer_application_id", type_="foreignkey")
        batch_op.drop_column("volunteer_application_id")
        batch_op.alter_column("registration_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("volunteer_applications", schema=None) as batch_op:
        batch_op.drop_constraint("uq_volunteer_application_qr_token", type_="unique")
        batch_op.drop_column("qr_token")
