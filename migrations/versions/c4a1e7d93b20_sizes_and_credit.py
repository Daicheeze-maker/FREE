"""sizes on products/cart/order items, and a credit balance on users

Revision ID: c4a1e7d93b20
Revises: b08840cdaef7
"""
from alembic import op
import sqlalchemy as sa

revision = "c4a1e7d93b20"
down_revision = "b08840cdaef7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("balance_minor", sa.Integer(), nullable=False, server_default="50000000"))
    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sizes", sa.String(length=120), nullable=True))
    with op.batch_alter_table("order_item", schema=None) as batch_op:
        batch_op.add_column(sa.Column("size", sa.String(length=20), nullable=True))
    with op.batch_alter_table("cart_item", schema=None) as batch_op:
        batch_op.add_column(sa.Column("size", sa.String(length=20), nullable=False, server_default=""))
        batch_op.drop_constraint("uq_cart_item_product", type_="unique")
        batch_op.create_unique_constraint("uq_cart_item_product_size", ["cart_id", "product_id", "size"])


def downgrade():
    with op.batch_alter_table("cart_item", schema=None) as batch_op:
        batch_op.drop_constraint("uq_cart_item_product_size", type_="unique")
        batch_op.create_unique_constraint("uq_cart_item_product", ["cart_id", "product_id"])
        batch_op.drop_column("size")
    with op.batch_alter_table("order_item", schema=None) as batch_op:
        batch_op.drop_column("size")
    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.drop_column("sizes")
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("balance_minor")
