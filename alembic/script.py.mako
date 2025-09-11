# -*- coding: utf-8 -*-
"""
Alembic 자동 생성 마이그레이션 스크립트 템플릿
- 이 파일은 'alembic revision --autogenerate' 실행 시 기본 템플릿으로 사용됩니다.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '${up_revision}'
down_revision = ${down_revision | repr}
branch_labels = ${branch_labels | repr}
depends_on = ${depends_on | repr}

def upgrade() -> None:
    """스키마 업그레이드 적용"""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """스키마 다운그레이드 적용(롤백)"""
    ${downgrades if downgrades else "pass"}
