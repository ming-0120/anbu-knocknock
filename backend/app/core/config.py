# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:1234@localhost:3306/anbu_knock_dev?charset=utf8mb4"
    ASYNC_DATABASE_URL: str = "mysql+aiomysql://root:1234@localhost:3306/anbu_knock_dev?charset=utf8mb4"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379  
    REDIS_DB: int = 0


settings = Settings()