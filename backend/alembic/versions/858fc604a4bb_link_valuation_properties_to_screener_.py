"""link valuation properties to screener listings

Revision ID: 858fc604a4bb
Revises: 4e331715de18
Create Date: 2026-09-17 16:14:14.050274

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "858fc604a4bb"
down_revision: str | Sequence[str] | None = "4e331715de18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FK_NAME = (
    "fk_valuation_properties_listing_id"  # named explicitly: autogenerate leaves it None, which makes downgrade fail
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("valuation_properties", schema=None) as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_valuation_properties_listing_id"), ["listing_id"], unique=False)
        batch_op.create_foreign_key(FK_NAME, "listings", ["listing_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("valuation_properties", schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_valuation_properties_listing_id"))
        batch_op.drop_column("listing_id")
