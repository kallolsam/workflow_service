import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    APP_NAME: str = "WorkflowExecutionService"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    DATABASE_URL: str

settings = Settings()
