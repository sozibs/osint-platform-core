"""Configuration settings for the Misinformation module."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class MisinformationSettings(BaseSettings):
    CLAIMBUSTER_API_KEY: str = ""
    GOOGLE_FACTCHECK_API_KEY: str = ""
    BOTOMETER_API_KEY: str = ""
    NEWSGUARD_API_KEY: str = ""

    CLAIMBUSTER_BASE_URL: str = "https://idir.uta.edu/claimbuster/api/v2"
    GOOGLE_FACTCHECK_BASE_URL: str = "https://factchecktools.googleapis.com/v1alpha1"

    CACHE_TTL_FACTCHECK: int = 3600
    CACHE_TTL_SOURCE_RATING: int = 86400

    class Config:
        env_file = ".env"
        extra = "ignore"


misinfo_settings = MisinformationSettings()
