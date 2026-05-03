"""
Application configuration settings.

All environment-specific values are loaded from .env file via pydantic-settings.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "Children's Literacy Learning Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", description="Environment: development/staging/production")
    DEBUG: bool = Field(default=True, description="Debug mode")
    
    # Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    
    # Database
    DATABASE_URL: str = Field(
        description="PostgreSQL connection string",
        default="postgresql+asyncpg://literacy_user:literacy_pass@localhost:5432/literacy_db"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, description="DB pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="DB max overflow")
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )
    
    # JWT
    JWT_SECRET_KEY: str = Field(
        default="your-super-secret-jwt-key-change-in-production",
        description="JWT signing secret key"
    )
    JWT_ACCESS_TOKEN_EXPIRES: int = Field(default=15, description="Access token expiry in minutes")
    JWT_REFRESH_TOKEN_EXPIRES: int = Field(default=7, description="Refresh token expiry in days")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    
    # Security
    BCRYPT_ROUNDS: int = Field(default=12, description="bcrypt cost factor")
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )
    
    # Rate Limiting
    RATE_LIMIT_AUTH: int = Field(default=5, description="Auth requests per minute")
    RATE_LIMIT_DEFAULT: int = Field(default=60, description="Default requests per minute")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
