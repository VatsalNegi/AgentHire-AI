from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentHire AI"
    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()

app = FastAPI(
    title=settings.app_name,
    description="Agentic AI interview platform",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "Welcome to AgentHire AI",
        "status": "running",
        "environment": settings.app_env,
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "agenthire-ai-api",
    }