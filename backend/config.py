from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Lecture Intelligence System"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    llm_backend: str = "huggingface"  # huggingface | openai | none
    hf_task: str = "text-generation"
    hf_chat_model: str = "distilgpt2"

    whisper_model_size: str = "base"
    whisper_compute_type: str = "int8"

    embed_backend: str = "sentence-transformers"  # sentence-transformers | openai
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    top_k_retrieval: int = 6
    chunk_max_chars: int = 850
    chunk_pause_threshold_sec: float = 1.5

    data_dir: Path = Path("db")
    artifacts_dir_name: str = "artifacts"
    chroma_dir_name: str = "chroma"


settings = Settings()
