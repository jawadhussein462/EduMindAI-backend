import os
import yaml
from typing import Optional
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int
    top_p: float
    frequency_penalty: float
    presence_penalty: float


class APIConfig(BaseModel):
    openai_api_key: str
    azure_formrecognizer_endpoint: Optional[str] = None
    azure_formrecognizer_key: Optional[str] = None


class ChatConfig(BaseModel):
    history_length: int


class AppConfig(BaseModel):
    llm: LLMConfig
    api: APIConfig
    chat: ChatConfig
    exams_path: Optional[str] = None
    vector_store: Optional[dict] = None


def load_config() -> AppConfig:
    """Load configuration from config.yaml file and return as AppConfig."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return AppConfig(**config) 