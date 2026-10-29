from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://lead_responder:local-development-password@db:5432/lead_responder"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: float = 30
    ghl_api_base_url: str = "https://services.leadconnectorhq.com"
    ghl_api_key: str = ""
    ghl_location_id: str = ""
    ghl_calendar_id: str = ""
    ghl_api_version: str = "v3"
    ghl_webhook_secret: str = ""
    business_timezone: str = "Australia/Brisbane"
    business_days: str = "MON,TUE,WED,THU,FRI"
    business_open_time: str = "09:00"
    business_close_time: str = "17:00"
    slot_length_minutes: int = 30
    minimum_notice_minutes: int = 120
    max_booking_days: int = 30
    service_name: str = "Your service"
    service_area: str = ""
    qualification_questions: str = "service,location,timeline"

    @property
    def configured_business_days(self) -> set[str]:
        return {day.strip().upper() for day in self.business_days.split(",") if day.strip()}

    @property
    def required_fields(self) -> list[str]:
        return [field.strip() for field in self.qualification_questions.split(",") if field.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
