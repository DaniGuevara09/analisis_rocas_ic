"""Tabla de configuración global (rangos de tamaño y colores, RF-14).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuracion",
        sa.Column("clave", sa.String(50), primary_key=True),
        sa.Column("valor", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("configuracion")
