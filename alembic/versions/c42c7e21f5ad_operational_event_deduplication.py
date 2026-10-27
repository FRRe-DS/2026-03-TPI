"""persist operational event deduplication

Revision ID: c42c7e21f5ad
Revises: da1fba108822
Create Date: 2026-10-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c42c7e21f5ad"
down_revision: Union[str, Sequence[str], None] = "da1fba108822"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eventos_operativos",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("conductor_id", sa.Uuid(), nullable=False),
        sa.Column("body_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(body_hash) = 64", name="ck_evento_operativo_hash_sha256"
        ),
        sa.CheckConstraint(
            "response_status BETWEEN 100 AND 599",
            name="ck_evento_operativo_response_status",
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("eventos_operativos")
