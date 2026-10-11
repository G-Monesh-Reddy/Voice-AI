"""Configuration management for Home Credit LAP Qualification Voice Agent."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application and business rules configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Environment
    environment: str = Field(default="development", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Logging verbosity")
    port: int = Field(default=8000, description="Server port")
    host: str = Field(default="0.0.0.0", description="Server bind host")

    # Business Rules Parameters
    company_name: str = Field(default="Home Credit", description="Company / Lender name")
    max_loan_amount: int = Field(default=7_500_000, description="Maximum loan offer amount (₹75 Lakhs)")
    min_tenure_years: int = Field(default=3, description="Minimum allowed tenure in years")
    max_tenure_years: int = Field(default=15, description="Maximum allowed tenure in years")

    # Agent Defaults
    default_agent_name: str = Field(default="Pooja", description="Default voice agent name")
    default_agent_gender: str = Field(default="female", description="Default voice agent gender (female/male)")
    default_language: str = Field(default="English", description="Default spoken language (English/Hindi)")

    # Mandatory LLM Provider: Google Gemini API
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.5-flash", description="Gemini model name")

    # Voice Platform Credentials (Optional for simulation, required for live deployment)
    retell_api_key: Optional[str] = Field(default=None, description="Retell AI API Key")
    retell_agent_id: Optional[str] = Field(default=None, description="Retell AI Agent ID")

    bolna_api_key: Optional[str] = Field(default=None, description="Bolna API Key")
    bolna_agent_id: Optional[str] = Field(default=None, description="Bolna Agent ID")


# Singleton configuration instance
settings = AppConfig()
