"""Enable pgvector and establish the DealMind migration baseline."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # vector may predate DealMind and other objects can depend on it.
    pass
