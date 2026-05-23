from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://trialmind:trialmind@localhost:5432/trialmind"
    model_dir: str = "/app/models"
    model_version: str = "v1"
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = ""
    log_level: str = "INFO"
    port: int = 8001

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
