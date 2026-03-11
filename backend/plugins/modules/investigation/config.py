"""Configuration settings for the Investigation module."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class InvestigationSettings(BaseSettings):
    NEWSAPI_KEY: str = ""
    SEC_EDGAR_BASE_URL: str = "https://data.sec.gov"
    GDELT_BASE_URL: str = "https://api.gdeltproject.org/api/v2"
    OPENCORPORATES_API_KEY: str = ""
    CACHE_TTL_NEWS: int = 1800
    CACHE_TTL_CORPORATE: int = 86400
    MAX_SEARCH_RESULTS: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"


inv_settings = InvestigationSettings()
