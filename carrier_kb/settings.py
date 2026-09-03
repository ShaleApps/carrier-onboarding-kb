from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kb_dsn: str = ""
    openai_api_key: str = ""
    embed_model: str = "text-embedding-3-large"
    answer_model: str = "gpt-5-mini"
    answer_synthesis_enabled: bool = False
    carrier_hub_api_base_url: str = "https://carrier-onboarding.lohi.ai"
    kb_capability_issuer: str = "carrier-onboarding-server"
    kb_capability_audience: str = "carrier-onboarding-kb"
    kb_capability_secret: str = ""
    lohi_read_dsn: str = ""
    ome_analytics_dsn: str = ""
