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
        # 간단한 캐시 및 타임스탬프
        self._cache: Dict[str, Any] = {}
        self._cache_mtime: Dict[str, float] = {}
        
    def load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """YAML 설정 파일 로드"""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            return {}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file) or {}
            # 캐싱
            self._cache[filename] = data
            try:
                self._cache_mtime[filename] = config_path.stat().st_mtime
            except Exception:
                pass
            return data
        except Exception as e:
            print(f"설정 파일 로드 오류 ({filename}): {e}")
            return {}
    
    def save_yaml_config(self, filename: str, config: Dict[str, Any]) -> bool:
        """YAML 설정 파일 저장"""
        config_path = self.config_dir / filename
        
        try:
            with open(config_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
            # 저장 후 캐시 갱신
            self._cache[filename] = config
            try:
                self._cache_mtime[filename] = config_path.stat().st_mtime
            except Exception:
                pass
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
    
    def expand_env_vars(self, value: Any) -> Any:
        """환경변수 확장 (${VAR_NAME} 형식) - 재귀적으로 dict/list 처리"""
        # 문자열 치환
        if isinstance(value, str):
            if value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                return os.getenv(env_var, value)
            return value
        # 리스트 재귀
        if isinstance(value, list):
            return [self.expand_env_vars(v) for v in value]
        # 딕셔너리 재귀
        if isinstance(value, dict):
            return {k: self.expand_env_vars(v) for k, v in value.items()}
        # 기타 타입은 그대로 반환
        return value

    def load_databases_config_expanded(self) -> Dict[str, Any]:
        """환경변수 확장을 적용한 데이터베이스 설정 반환"""
        raw = self.load_databases_config()
        return self.expand_env_vars(raw)

    def validate_databases_config(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """databases.yaml 유효성 검증
        - 필수 키: databases
        - 각 항목 필수: name, host, port, database, username, password, environment, priority
        """
        result = {"valid": True, "errors": [], "total": 0}
        data = config if config is not None else self.load_databases_config_expanded()
        if not isinstance(data, dict) or "databases" not in data:
            result["valid"] = False
            result["errors"].append("루트에 'databases' 키가 없습니다.")
            return result
        dbs = data.get("databases", {})
        if not isinstance(dbs, dict) or not dbs:
            result["valid"] = False
            result["errors"].append("'databases' 항목이 비어있거나 잘못된 형식입니다.")
            return result
        required = ["name", "host", "port", "database", "username", "password", "environment", "priority"]
        for key, conf in dbs.items():
            result["total"] += 1
            if not isinstance(conf, dict):
                result["valid"] = False
                result["errors"].append(f"{key}: 항목이 객체(dict)가 아닙니다.")
                continue
            missing = [f for f in required if f not in conf]
            if missing:
                result["valid"] = False
                result["errors"].append(f"{key}: 필수 필드 누락 - {', '.join(missing)}")
            # 타입/값 간단 체크
            try:
                if "port" in conf and conf["port"] is not None:
                    int(conf["port"])  # 숫자 변환 가능 여부
            except Exception:
                result["valid"] = False
                result["errors"].append(f"{key}: port는 정수여야 합니다.")
        return result

    def needs_reload(self, filename: str) -> bool:
        """파일 변경 여부 확인"""
        path = self.config_dir / filename
        try:
            mtime = path.stat().st_mtime
            return self._cache_mtime.get(filename) != mtime
        except Exception:
            return True

    def reload_databases_config(self) -> Dict[str, Any]:
        """databases.yaml 강제 리로드 (캐시 무시)"""
        # 캐시 무시: 직접 읽기
        config_path = self.config_dir / "databases.yaml"
        if not config_path.exists():
            self._cache.pop("databases.yaml", None)
            self._cache_mtime.pop("databases.yaml", None)
            return {}
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        self._cache["databases.yaml"] = data
        try:
            self._cache_mtime["databases.yaml"] = config_path.stat().st_mtime
        except Exception:
            pass
        return data

# 전역 설정 인스턴스
settings = Settings()
config_manager = ConfigManager()

def get_settings() -> Settings:
    """설정 인스턴스 반환"""
    return settings

def get_config_manager() -> ConfigManager:
    """설정 관리자 인스턴스 반환"""
    return config_manager
