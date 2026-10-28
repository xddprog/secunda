from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[3]


class Config(
    BaseSettings,
    env_file=BASE_DIR / ".env",
    case_sensitive=True,
    extra="ignore",
):
    pass


class DatabaseConfig(Config):
    DB_NAME: str = "payments"
    DB_USER: str = "payments"
    DB_PASS: str = "payments"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    def get_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


class RabbitMQConfig(Config):
    URL: str = Field(
        default="amqp://payments:payments@localhost:5672/",
        validation_alias="RABBITMQ_URL",
    )


class AppConfig(Config):
    API_KEY: str = "test-api-key"


DB_CONFIG = DatabaseConfig()
RABBITMQ_CONFIG = RabbitMQConfig()
APP_CONFIG = AppConfig()
