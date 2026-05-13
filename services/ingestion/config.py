from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://trialmind:trialmind@localhost:5432/trialmind"
    ct_api_base: str = "https://clinicaltrials.gov/api/v2"
    batch_size: int = 100
    max_trials: int = 50000
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
