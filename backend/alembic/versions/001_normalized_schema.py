"""Normalized schema with analysis_errors table."""

from alembic import op
import sqlalchemy as sa


revision = "001_normalized_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            total_errors_found INTEGER NOT NULL DEFAULT 0 CHECK (total_errors_found >= 0),
            total_analyzed INTEGER NOT NULL DEFAULT 0 CHECK (total_analyzed >= 0),
            status VARCHAR(20) DEFAULT 'completed',
            data JSONB DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_errors (
            id BIGSERIAL PRIMARY KEY,
            analysis_id BIGINT REFERENCES analyses(id) ON DELETE CASCADE,
            line_number INTEGER,
            level VARCHAR(20),
            message TEXT,
            category VARCHAR(50),
            explanation TEXT,
            causes JSONB DEFAULT '[]'::jsonb,
            solutions JSONB DEFAULT '[]'::jsonb,
            analyzed_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_errors_analysis ON analysis_errors(analysis_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analysis_errors")
    op.execute("DROP TABLE IF EXISTS analyses")
