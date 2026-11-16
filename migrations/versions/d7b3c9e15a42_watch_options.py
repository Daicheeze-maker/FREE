"""watch options: colours and engraving on products, wider option text on cart/order lines

Revision ID: d7b3c9e15a42
Revises: c4a1e7d93b20
"""
from alembic import op
import sqlalchemy as sa

revision = "d7b3c9e15a42"
down_revision = "c4a1e7d93b20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.add_column(sa.Column("colors", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("engraving_fee_minor", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("engraving_max", sa.Integer(), nullable=False, server_default="20"))
    with op.batch_alter_table("order_item", schema=None) as batch_op:
        batch_op.alter_column("size", existing_type=sa.String(length=20), type_=sa.String(length=160), existing_nullable=True)
    with op.batch_alter_table("cart_item", schema=None) as batch_op:
        batch_op.alter_column("size", existing_type=sa.String(length=20), type_=sa.String(length=160),
                              existing_nullable=False, existing_server_default="")


def downgrade():
    with op.batch_alter_table("cart_item", schema=None) as batch_op:
        batch_op.alter_column("size", existing_type=sa.String(length=160), type_=sa.String(length=20),
                              existing_nullable=False, existing_server_default="")
    with op.batch_alter_table("order_item", schema=None) as batch_op:
        batch_op.alter_column("size", existing_type=sa.String(length=160), type_=sa.String(length=20), existing_nullable=True)
    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.drop_column("engraving_max")
        batch_op.drop_column("engraving_fee_minor")
        batch_op.drop_column("colors")
