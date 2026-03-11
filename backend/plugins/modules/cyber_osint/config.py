"""Configuration settings for the Cyber OSINT module."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class CyberOsintSettings(BaseSettings):
    VIRUSTOTAL_API_KEY: str = ""
    ABUSEIPDB_API_KEY: str = ""
    SHODAN_API_KEY: str = ""
    CENSYS_API_ID: str = ""
    CENSYS_API_SECRET: str = ""
    URLHAUS_BASE_URL: str = "https://urlhaus-api.abuse.ch/v1"

    CACHE_TTL_IP: int = 3600
    CACHE_TTL_DOMAIN: int = 3600
    CACHE_TTL_THREAT: int = 300

    class Config:
        env_file = ".env"
        extra = "ignore"


cyber_settings = CyberOsintSettings()
