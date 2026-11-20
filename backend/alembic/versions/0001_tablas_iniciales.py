"""Tablas iniciales: analisis, calibracion, region_excluida y fragmento.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analisis",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("imagen_ruta", sa.String(255), nullable=False),
        sa.Column("imagen_ancho_px", sa.Integer(), nullable=False),
        sa.Column("imagen_alto_px", sa.Integer(), nullable=False),
        sa.Column("imagen_formato", sa.String(3), nullable=False),
    )
    op.create_table(
        "calibracion",
        sa.Column(
            "analisis_id",
            sa.Uuid(),
            sa.ForeignKey("analisis.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("inicio_x_px", sa.Float(), nullable=False),
        sa.Column("inicio_y_px", sa.Float(), nullable=False),
        sa.Column("fin_x_px", sa.Float(), nullable=False),
        sa.Column("fin_y_px", sa.Float(), nullable=False),
        sa.Column("longitud_real_mm", sa.Float(), nullable=False),
    )
    op.create_table(
        "region_excluida",
        sa.Column(
            "analisis_id",
            sa.Uuid(),
            sa.ForeignKey("analisis.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("poligono", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "fragmento",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "analisis_id",
            sa.Uuid(),
            sa.ForeignKey("analisis.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("poligono", postgresql.JSONB(), nullable=False),
        sa.Column("origen", sa.String(10), nullable=False),
    )
    op.create_index("ix_fragmento_analisis_id", "fragmento", ["analisis_id"])


def downgrade() -> None:
    op.drop_index("ix_fragmento_analisis_id", table_name="fragmento")
    op.drop_table("fragmento")
    op.drop_table("region_excluida")
    op.drop_table("calibracion")
    op.drop_table("analisis")
