from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://trialmind:trialmind@localhost:5432/trialmind"
    mcp_server_command: str = "python"
    mcp_server_script: str = "/app/mcp-server/server.py"
    ml_service_url: str = "http://ml:8001"
    aws_region: str = "us-east-1"
    aws_bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    max_iterations: int = 15
    log_level: str = "INFO"
    port: int = 8002

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
