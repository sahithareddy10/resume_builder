"""
Application configuration using Pydantic Settings.

All configuration is driven by environment variables.
No hardcoded secrets.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	"""Application settings."""
	APP_NAME: str = "AI Resume Optimizer"
	APP_VERSION: str = "1.0.0"
	ENVIRONMENT: str = "development"
	DEBUG: bool = True

	API_V1_PREFIX: str = "/api/v1"
	BACKEND_CORS_ORIGINS: str = "http://localhost:3001"

	HOST: str = "0.0.0.0"
	PORT: int = 8001
	WORKERS: int = 1

	MODEL_NAME: str = "qwen2.5:1.5b"
	BASE_MODEL: str = "qwen2.5:1.5b"
	ADAPTER_PATH: str = ""
	DEVICE: str = "cpu"
	MAX_NEW_TOKENS: int = 900
	TEMPERATURE: float = 0.2
	TOP_P: float = 0.9
	LOAD_MODEL_AT_STARTUP: bool = True
	MODEL_TIMEOUT: int = 600
	OLLAMA_HOST: str = "http://127.0.0.1:11434"
	OLLAMA_MODEL: str = "resume-optimizer"
	CANDIDATE_VERSIONS: int = 1

	LOAD_IN_4BIT: bool = True

	UPLOAD_DIR: str = "./uploads"
	OUTPUT_DIR: str = "./outputs"
	MAX_UPLOAD_SIZE_MB: int = 10
	ALLOWED_EXTENSIONS: str = "pdf,docx,txt"

	EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

	REDIS_URL: str = "redis://localhost:6379/0"
	CELERY_BROKER_URL: str = "redis://localhost:6379/1"
	CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
	USE_CELERY: bool = False

	SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"

	model_config = SettingsConfigDict(
		env_file=str(Path(__file__).resolve().parents[2] / ".env"),
		env_file_encoding="utf-8",
		extra="ignore",
	)

	@property
	def cors_origins(self) -> list[str]:
		return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",")]

	@property
	def allowed_extensions(self) -> set[str]:
		return {e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",")}

	@property
	def max_upload_size(self) -> int:
		return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
