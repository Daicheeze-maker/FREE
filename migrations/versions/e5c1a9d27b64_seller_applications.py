"""seller applications: buyers apply to sell, an admin approves

Revision ID: e5c1a9d27b64
Revises: d7b3c9e15a42
"""
from alembic import op
import sqlalchemy as sa

revision = "e5c1a9d27b64"
down_revision = "d7b3c9e15a42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "seller_application",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_name", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("about", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_seller_application_user_id", "seller_application", ["user_id"])
    op.create_index("ix_seller_application_status", "seller_application", ["status"])


def downgrade():
    op.drop_index("ix_seller_application_status", table_name="seller_application")
    op.drop_index("ix_seller_application_user_id", table_name="seller_application")
    op.drop_table("seller_application")
