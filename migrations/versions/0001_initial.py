"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "raw_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "knowledge_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "raw_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_sources.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "supersedes",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_cards.id"),
            nullable=True,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_knowledge_cards_active", "knowledge_cards", ["active"])
    op.execute(
        "CREATE INDEX ix_knowledge_cards_embedding_hnsw ON knowledge_cards "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_cards_embedding_hnsw", table_name="knowledge_cards")
    op.drop_index("ix_knowledge_cards_active", table_name="knowledge_cards")
    op.drop_table("knowledge_cards")
    op.drop_table("raw_sources")
    op.execute("DROP EXTENSION IF EXISTS vector")
