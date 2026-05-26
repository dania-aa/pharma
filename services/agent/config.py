from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://trialmind:trialmind@localhost:5432/trialmind"
    mcp_server_command: str = "python"
    mcp_server_script: str = "/app/mcp-server/server.py"
    ml_service_url: str = "http://ml:8001"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    max_iterations: int = 15
    log_level: str = "INFO"
    port: int = 8002

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
