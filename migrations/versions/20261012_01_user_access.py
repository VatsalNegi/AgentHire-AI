"""Add default-denied application access to user profiles."""

from alembic import op
import sqlalchemy as sa


revision = "20261012_01"
down_revision = "20260605_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "is_active", schema="public")
