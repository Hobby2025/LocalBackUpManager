# -*- coding: utf-8 -*-
"""
Alembic 환경 설정
- 애플리케이션의 SQLAlchemy 메타데이터를 로드하여 마이그레이션을 수행
- DATABASE_URL은 app.config.Settings 에서 로드
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# 프로젝트 루트 경로를 sys.path에 추가 (alembic 실행 위치와 상관없이 import 가능하도록)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 앱의 메타데이터 로드
from app.database import Base  # SQLAlchemy Base (모델 메타데이터)
from app.config import settings  # DATABASE_URL 등 설정

# Alembic Config 객체: alembic.ini의 값들에 접근
config = context.config

# 로깅 설정 적용 (alembic.ini 기준)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 대상 메타데이터 설정: autogenerate에 필요
# - 모델 변경사항을 자동 감지하여 마이그레이션 생성 가능
# - 주의: 동적 생성 테이블 등은 수동 반영 필요

target_metadata = Base.metadata

# 데이터베이스 URL 구성: settings에서 가져와 alembic 설정에 주입
# - alembic.ini의 sqlalchemy.url 대신 여기서 설정값을 덮어씀
if settings.DATABASE_URL:
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """오프라인 모드로 마이그레이션 실행
    - 실제 DB 연결 없이 SQL 스크립트만 생성
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,  # 타입 변경 감지
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드로 마이그레이션 실행
    - 실제 DB에 연결하여 마이그레이션 적용
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 타입 변경 감지
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
