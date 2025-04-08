from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """
    Configuration settings for the terminus application.

    Attributes
    ----------
    database_url : str
        The connection string for the database.
    log_level : str
        The logging level for the application.
    llm_model : str
        The model name for the large language model (LLM) used in the application.
    topic_domain : str
        The domain of the topic for which the LLM is configured (e.g., finance).
    """

    # Pydantic Settings configuration
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default configuration values
    database_url: str = "sqlite:///./terminus.db"
    log_level: str = "INFO"
    llm_model: str = "gemini/gemini-2.0-flash"
    topic_domain: str = "finance"
    topic_keywords: List[str] = [
        "finance",
        "financial",
        "banking",
        "investment",
        "economic",
        "stock",
        "market",
        "derivative",
    ]


# Create a global settings instance that can be imported elsewhere.
# If you want to disable loading from any .env file, pass _env_file=None:
# settings = Settings(_env_file=None)
settings = Settings()
