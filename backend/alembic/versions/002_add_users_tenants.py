"""Add users and tenants tables for multi-tenant RBAC."""

from alembic import op
import sqlalchemy as sa

revision = "002_add_users_tenants"
down_revision = "001_normalized_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create tenants table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            plan VARCHAR(50) DEFAULT 'free'
        )
        """
    )
    # 2. Create users table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
            email VARCHAR(255) UNIQUE NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'viewer',
            hashed_password VARCHAR(255) NOT NULL
        )
        """
    )
    # 3. Add columns to analyses table (make them nullable for backwards compatibility)
    try:
        op.execute("ALTER TABLE analyses ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)")
    except Exception:
        try:
            op.execute("ALTER TABLE analyses ADD COLUMN tenant_id INTEGER")
        except Exception:
            pass

    try:
        op.execute("ALTER TABLE analyses ADD COLUMN user_id INTEGER REFERENCES users(id)")
    except Exception:
        try:
            op.execute("ALTER TABLE analyses ADD COLUMN user_id INTEGER")
        except Exception:
            pass


def downgrade() -> None:
    # Remove columns from analyses
    try:
        op.execute("ALTER TABLE analyses DROP COLUMN user_id")
    except Exception:
        pass
    try:
        op.execute("ALTER TABLE analyses DROP COLUMN tenant_id")
    except Exception:
        pass
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS tenants")
