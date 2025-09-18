"""Add db_type column to databases table

Revision ID: 20250918_add_db_type
Revises: 
Create Date: 2025-09-18 10:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250918_add_db_type'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """데이터베이스 스키마 업그레이드: db_type 컬럼 추가"""
    
    # databases 테이블에 db_type 컬럼 추가
    # 기본값을 'postgresql'로 설정하여 기존 레코드와의 호환성 보장
    op.add_column('databases', sa.Column('db_type', sa.String(length=20), nullable=False, server_default='postgresql'))
    
    # 기존 데이터에 대해 기본값 설정 후 server_default 제거
    # 이는 새로운 레코드에 대해서는 애플리케이션 레벨에서 기본값을 관리하기 위함
    op.alter_column('databases', 'db_type', server_default=None)
    
    # db_type 컬럼에 대한 인덱스 추가 (조회 성능 최적화)
    op.create_index('ix_databases_db_type', 'databases', ['db_type'])
    
    # db_type과 environment 조합 인덱스 추가 (환경별 DB 타입 조회 최적화)
    op.create_index('ix_databases_db_type_environment', 'databases', ['db_type', 'environment'])


def downgrade() -> None:
    """데이터베이스 스키마 다운그레이드: db_type 컬럼 제거"""
    
    # 인덱스 제거
    op.drop_index('ix_databases_db_type_environment', table_name='databases')
    op.drop_index('ix_databases_db_type', table_name='databases')
    
    # db_type 컬럼 제거
    op.drop_column('databases', 'db_type')
