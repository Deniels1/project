from app.config import get_settings


def test_settings_loads_defaults() -> None:
    settings = get_settings()
    assert settings.APP_NAME == "Children's Literacy Learning Platform"
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_ACCESS_TOKEN_EXPIRES == 15
