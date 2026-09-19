from pydantic import PositiveFloat
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/hackspain"
    secret_key: str = "change-me-in-production"
    debug: bool = True
    typesafe_api_key: str = ""
    helmcode_base_url: str = "https://api.helmcode.com/v1"
    helmcode_api_key: str = ""
    supervisor_model: str = ""
    watcher_tau: float = 0.6
    watcher_persistence: int = 1
    action_gate: float = 0.7
    short_term_n: int = 20
    run_log_dir: str = "/var/lib/hackspain/runs"
    action_step_delay: float = 0.35
    action_dispatch_token: str = ""
    happyrobot_api_key: str = ""
    happyrobot_hook_url: str = ""
    happyrobot_api_base: str = ""
    oncall_phone: str = ""
    oncall_name: str = ""
    happyrobot_poll_interval: PositiveFloat = 1.5
    happyrobot_poll_timeout: PositiveFloat = 240

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return "postgresql+psycopg://" + self.database_url.removeprefix("postgresql://")
        return self.database_url


settings = Settings()
