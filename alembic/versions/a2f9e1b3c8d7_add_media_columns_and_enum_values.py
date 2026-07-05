"""add_media_columns_and_enum_values

Revision ID: a2f9e1b3c8d7
Revises: c133d7fd61b6
Create Date: 2026-06-28 22:00:00.000000

Couvre les changements de schéma qui étaient gérés manuellement
par check_and_update_schema() dans le lifespan FastAPI.
Cette migration est idempotente (utilise IF NOT EXISTS / IF EXISTS).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a2f9e1b3c8d7'
down_revision: Union[str, Sequence[str], None] = 'c133d7fd61b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajout des colonnes média + valeurs d'enum manquantes."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Table orders : colonnes has_audio et has_poster
    # ------------------------------------------------------------------
    inspector = sa.inspect(conn)
    orders_columns = [c['name'] for c in inspector.get_columns('orders')]

    if 'has_audio' not in orders_columns:
        op.add_column(
            'orders',
            sa.Column('has_audio', sa.Boolean(), nullable=False, server_default=sa.text('false'))
        )

    if 'has_poster' not in orders_columns:
        op.add_column(
            'orders',
            sa.Column('has_poster', sa.Boolean(), nullable=False, server_default=sa.text('false'))
        )

    # ------------------------------------------------------------------
    # 2. Table astrological_reports : colonnes audio_url et poster_url
    # ------------------------------------------------------------------
    reports_columns = [c['name'] for c in inspector.get_columns('astrological_reports')]

    if 'audio_url' not in reports_columns:
        op.add_column(
            'astrological_reports',
            sa.Column('audio_url', sa.String(length=512), nullable=True)
        )

    if 'poster_url' not in reports_columns:
        op.add_column(
            'astrological_reports',
            sa.Column('poster_url', sa.String(length=512), nullable=True)
        )

    # ------------------------------------------------------------------
    # 3. Enum plan_type_enum : valeurs annee_cosmique et cosmos_integral
    #    ALTER TYPE ... ADD VALUE doit s'exécuter hors transaction.
    # ------------------------------------------------------------------
    existing_enum_values = conn.execute(
        sa.text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'plan_type_enum'"
        )
    ).scalars().all()

    # Alembic n'expose pas de primitive native pour ADD VALUE IF NOT EXISTS
    # avant PostgreSQL 9.6; on vérifie manuellement.
    if 'annee_cosmique' not in existing_enum_values:
        # Doit s'exécuter en AUTOCOMMIT
        op.execute(sa.text("ALTER TYPE plan_type_enum ADD VALUE 'annee_cosmique'"))

    if 'cosmos_integral' not in existing_enum_values:
        op.execute(sa.text("ALTER TYPE plan_type_enum ADD VALUE 'cosmos_integral'"))


def downgrade() -> None:
    """
    PostgreSQL ne supporte pas la suppression de valeurs d'enum.
    Pour les colonnes on peut les supprimer proprement.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    reports_columns = [c['name'] for c in inspector.get_columns('astrological_reports')]
    if 'poster_url' in reports_columns:
        op.drop_column('astrological_reports', 'poster_url')
    if 'audio_url' in reports_columns:
        op.drop_column('astrological_reports', 'audio_url')

    orders_columns = [c['name'] for c in inspector.get_columns('orders')]
    if 'has_poster' in orders_columns:
        op.drop_column('orders', 'has_poster')
    if 'has_audio' in orders_columns:
        op.drop_column('orders', 'has_audio')
    # Note : les valeurs d'enum ne peuvent pas être supprimées sans recréer le type.
