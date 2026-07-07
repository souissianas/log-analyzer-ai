"""Add status and created_at columns to users table.

These columns were previously added via manual ALTER TABLE statements in
services/storage.py:init_db(). This migration supersedes that approach --
all future schema changes must go through Alembic, not application code.
"""

from alembic import op
import sqlalchemy as sa

revision = "003_add_users_status_created_at"
down_revision = "002_add_users_tenants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add status column (safe to re-run -- uses IF NOT EXISTS)
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'pending'
        """
    )
    # Add created_at column
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS status")
