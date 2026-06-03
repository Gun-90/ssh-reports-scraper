import os
import json
from loguru import logger


class MissingConfigError(ValueError):
    """Required runtime configuration is missing from a loaded config source."""


class ConfigManager:
    _instance = None
    _secrets = {}
    _env = 'prod'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        # 1. 환경변수 ENV (dev or prod) 확인
        raw_env = os.getenv('ENV', 'prod').lower()
        if 'dev' in raw_env:
            self._env = 'dev'
        else:
            self._env = 'prod'

        # 2. 외부 JSON 로드
        self._has_secrets = False
        secrets_path = os.path.expanduser("~/secrets/ssh-reports-scraper/secrets.json")
        try:
            if os.path.exists(secrets_path):
                with open(secrets_path, 'r', encoding='utf-8') as f:
                    self._secrets = json.load(f)
                self._has_secrets = True
            else:
                self._secrets = {"common": {}, "dev": {}, "prod": {}}
        except Exception as e:
            self._secrets = {"common": {}, "dev": {}, "prod": {}}

    def has_secrets(self):
        return self._has_secrets

    @property
    def ENV(self):
        return self._env

    @property
    def DB_PATH(self):
        # 1순위: 환경변수 SQLITE_DB_PATH
        env_path = os.getenv('SQLITE_DB_PATH')
        if env_path: return os.path.expanduser(env_path)
        
        # 2순위: 환경별 전용 DB_PATH (dev -> telegram_dev.db / prod -> telegram.db)
        env_secrets = self._secrets.get(self._env, {})
        path = env_secrets.get("DB_PATH")
        
        if not path:
            # 3순위: 공통 설정 (common -> SQLITE_DB_PATH)
            path = self._secrets.get("common", {}).get("SQLITE_DB_PATH")
            
        return os.path.expanduser(path or "~/sqlite3/telegram.db")

    @property
    def BOT_TOKEN(self):
        return self._secrets.get(self._env, {}).get("BOT_TOKEN") or self._secrets.get("common", {}).get("TELEGRAM_BOT_TOKEN_REPORT_ALARM_SECRET")

    @property
    def CHANNEL_ID(self):
        return self._secrets.get(self._env, {}).get("CHANNEL_ID") or self._secrets.get("common", {}).get("TELEGRAM_CHANNEL_ID_REPORT_ALARM")

    def get_secret(self, key, default=None):
        """특정 환경 변수 또는 공통 변수를 가져옵니다."""
        val = os.getenv(key)
        if val: return val
        return self._secrets.get("common", {}).get(key, default)

    def get_urls(self, key, default=None):
        """증권사 URL 목록 반환.
        우선순위: 1) env var `urls` JSON (generate_env.py) → 2) env var URLS_{key} → 3) secrets.json 직접 읽기

        secrets/.env가 아예 없는 CI·dry-run 환경은 기존처럼 default/[]를 반환한다.
        반대로 URL 설정 소스가 로드됐는데 요청한 key만 없으면 운영 설정 누락으로 보고 즉시 실패시킨다.
        """
        config_source_loaded = False

        # 1) generate_env.py가 .env에 쓰는 urls 키 (전체 JSON)
        env_urls = os.getenv("urls")
        if env_urls:
            config_source_loaded = True
            try:
                all_urls = json.loads(env_urls)
                if key in all_urls:
                    return all_urls[key]
            except json.JSONDecodeError as e:
                raise MissingConfigError(f"Invalid urls JSON env var: {e}") from e

        # 2) 개별 URLS_{key} 환경변수
        env_val = os.getenv(f"URLS_{key}")
        if env_val:
            config_source_loaded = True
            try:
                return json.loads(env_val)
            except json.JSONDecodeError as e:
                raise MissingConfigError(f"Invalid URLS_{key} JSON env var: {e}") from e

        # 3) secrets.json 직접 읽기 (현재 프로덕션)
        secret_urls = self._secrets.get("urls", {})
        if secret_urls:
            config_source_loaded = True
            if key in secret_urls:
                return secret_urls[key]

        if default is not None:
            return default

        if config_source_loaded:
            raise MissingConfigError(f"Missing urls config for key: {key}")

        return []

    def get_base_url(self, key, default=""):
        """첫 번째 URL에서 scheme+netloc 추출."""
        from urllib.parse import urlparse
        urls = self.get_urls(key)
        if urls and isinstance(urls, list) and urls[0]:
            p = urlparse(urls[0])
            return f"{p.scheme}://{p.netloc}"
        return default

# 싱글톤 인스턴스
config = ConfigManager()

if __name__ == "__main__":
    # 디버깅 출력 추가
    # print(f"Raw Secrets Dev: {config._secrets.get('dev')}")
    print(f"Current ENV: {config.ENV}")
    print(f"DB Path: {config.DB_PATH}")
    print(f"Token (First 5): {str(config.BOT_TOKEN)[:5]}...")
