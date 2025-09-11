"""
Phase1.3: 트리거 및 뷰 추가 (backups)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# 리비전 식별자
revision = 'e9b1b2c3d4e5'
down_revision = 'd6802b63c966'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """업그레이드: 트리거 함수/트리거/뷰 생성"""
    # 트리거 함수: 백업 완료 시 완료시간/소요시간 자동 설정
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION set_backup_completion_fields()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.status = 'completed' THEN
                    IF NEW.completed_at IS NULL THEN
                        NEW.completed_at := NOW();
                    END IF;
                    IF NEW.started_at IS NOT NULL AND NEW.completed_at IS NOT NULL THEN
                        NEW.duration_seconds := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at))::INT;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # 트리거 생성
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'backups_set_completion_fields'
                ) THEN
                    CREATE TRIGGER backups_set_completion_fields
                    BEFORE INSERT OR UPDATE ON backups
                    FOR EACH ROW EXECUTE FUNCTION set_backup_completion_fields();
                END IF;
            END$$;
            """
        )
    )

    # 뷰: DB별 백업 요약
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW v_backup_summary_by_db AS
            SELECT
                database_id,
                COUNT(*) AS total_backups,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed_backups,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_backups,
                MAX(created_at) AS last_created_at,
                MAX(completed_at) AS last_completed_at
            FROM backups
            GROUP BY database_id;
            """
        )
    )

    # 뷰: 최근 7일 백업 목록
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW v_recent_backups AS
            SELECT *
            FROM backups
            WHERE created_at >= NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC;
            """
        )
    )


def downgrade() -> None:
    """다운그레이드: 뷰/트리거/함수 삭제"""
    # 뷰 삭제
    op.execute(sa.text("DROP VIEW IF EXISTS v_recent_backups"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_backup_summary_by_db"))

    # 트리거 삭제
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'backups_set_completion_fields'
                ) THEN
                    DROP TRIGGER backups_set_completion_fields ON backups;
                END IF;
            END$$;
            """
        )
    )

    # 함수 삭제
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_backup_completion_fields"))
