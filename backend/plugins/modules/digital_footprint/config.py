"""Configuration settings for the Digital Footprint module."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class DigitalFootprintSettings(BaseSettings):
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    HAVEIBEENPWNED_API_KEY: str = ""
    HUNTER_IO_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    WHOIS_API_KEY: str = ""

    CACHE_TTL_SOCIAL_PROFILE: int = 3600
    CACHE_TTL_WHOIS: int = 86400
    CACHE_TTL_EMAIL: int = 3600

    class Config:
        env_file = ".env"
        extra = "ignore"


df_settings = DigitalFootprintSettings()
