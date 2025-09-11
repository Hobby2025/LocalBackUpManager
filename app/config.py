"""
애플리케이션 설정 관리
환경변수 및 YAML 설정 파일 처리
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

class Settings(BaseSettings):
    """애플리케이션 기본 설정"""
    
    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # 데이터베이스 설정
    # 기본값은 PostgreSQL(psycopg2 동기 드라이버) 사용
    # 환경변수 DATABASE_URL이 지정되면 해당 값을 우선 사용
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # PostgreSQL 개별 설정 (DATABASE_URL이 없을 때 사용)
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: int = int(os.getenv("DB_PORT"))
    DB_NAME: str = os.getenv("DB_NAME")
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    
    # 백업 설정
    BACKUP_BASE_PATH: str = "./data/backups"
    TEMP_PATH: str = "./data/temp"
    MAX_PARALLEL_JOBS: int = 3
    DEFAULT_COMPRESSION: str = "gzip"
    DEFAULT_ENCRYPTION: bool = True
    
    # 보안 설정
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    
    # 로깅 설정
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "./data/logs/app.log"
    LOG_MAX_SIZE: str = "10MB"
    LOG_BACKUP_COUNT: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = True

class ConfigManager:
    """설정 파일 관리자"""
    
    def __init__(self):
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        
    def load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """YAML 설정 파일 로드"""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            return {}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        except Exception as e:
            print(f"설정 파일 로드 오류 ({filename}): {e}")
            return {}
    
    def save_yaml_config(self, filename: str, config: Dict[str, Any]) -> bool:
        """YAML 설정 파일 저장"""
        config_path = self.config_dir / filename
        
        try:
            with open(config_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"설정 파일 저장 오류 ({filename}): {e}")
            return False
    
    def load_databases_config(self) -> Dict[str, Any]:
        """데이터베이스 설정 로드"""
        return self.load_yaml_config("databases.yaml")
    
    def save_databases_config(self, config: Dict[str, Any]) -> bool:
        """데이터베이스 설정 저장"""
        return self.save_yaml_config("databases.yaml", config)
    
    def load_app_settings(self) -> Dict[str, Any]:
        """애플리케이션 설정 로드"""
        return self.load_yaml_config("settings.yaml")
    
    def get_database_config(self, db_id: str) -> Optional[Dict[str, Any]]:
        """특정 데이터베이스 설정 조회"""
        databases_config = self.load_databases_config()
        return databases_config.get("databases", {}).get(db_id)
    
    def expand_env_vars(self, value: str) -> str:
        """환경변수 확장 (${VAR_NAME} 형식)"""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, value)
        return value

# 전역 설정 인스턴스
settings = Settings()
config_manager = ConfigManager()

def get_settings() -> Settings:
    """설정 인스턴스 반환"""
    return settings

def get_config_manager() -> ConfigManager:
    """설정 관리자 인스턴스 반환"""
    return config_manager
