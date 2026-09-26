from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: str = Field(default="")
    github_token: str = Field(default="")
    db_path: str = Field(default="data/traces.db")

settings = Settings()
