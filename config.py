from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file= ".env", # for saving secret keys
        env_file_encoding="utf-8"
    )
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    max_upload_size_bytes: int = 5*1024*1024

settings = Settings() #loaded from .env file