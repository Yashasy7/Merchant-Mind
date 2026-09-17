"""
Tests for application configuration loading and validation.
"""

from app.core.config import Settings, get_settings


def test_settings_load_defaults():
    """Verify that settings initialize with sensible default values."""
    settings = Settings()
    assert settings.app_name == "Paytm MerchantMind API"
    assert settings.app_env in ["development", "production", "test"]
    assert settings.app_port == 8000
    assert settings.demo_merchant_id == "demo-merchant-001"
    assert settings.seed_random_seed == 42


def test_get_settings_cached_singleton():
    """Verify that get_settings() returns a cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_cors_origins_parsing():
    """Verify that CORS origins can parse JSON string, comma-separated string, or list."""
    s = Settings(CORS_ORIGINS='["http://example.com", "http://localhost:5173"]')
    assert "http://example.com" in s.cors_origins
    assert "http://localhost:5173" in s.cors_origins

    s_csv = Settings(CORS_ORIGINS="http://localhost:3000, http://localhost:5173")
    assert "http://localhost:3000" in s_csv.cors_origins
    assert "http://localhost:5173" in s_csv.cors_origins
