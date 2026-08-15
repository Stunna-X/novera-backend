"""repair role permission assignments

Revision ID: 245083dcf1b7
Revises: a7f4c2d9e1b6
Create Date: 2026-08-13 00:05:04.547577

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# Revision identifiers used by Alembic.
revision: str = '245083dcf1b7'
down_revision: Union[str, Sequence[str], None] = 'a7f4c2d9e1b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    pass


def downgrade() -> None:
    """Downgrade schema."""

    pass
