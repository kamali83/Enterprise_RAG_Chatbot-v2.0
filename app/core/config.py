"""
Enterprise RAG Chatbot Configuration
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, Field
from typing import Optional, List
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Enterprise RAG Chatbot"
    APP_VERSION: str = "2.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/rag_chatbot"
    DATABASE_ASYNC_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rag_chatbot"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Authentication
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # LLM Configuration
    LLM_PROVIDER: str = "local"  # local, openai, ollama, vllm, groq, together
    MODEL_NAME: str = "google/flan-t5-large"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OLLAMA_MODEL: str = "llama2"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # vLLM Configuration (for high-performance local inference)
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    VLLM_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.2"
    
    # Groq Configuration (for ultra-fast cloud inference)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama3-70b-8192"
    
    # Together AI Configuration
    TOGETHER_API_KEY: Optional[str] = None
    TOGETHER_MODEL: str = "mistralai/Mixtral-8x7B-Instruct-v0.1"

    # RAG Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_K: int = 5
    USE_RERANKING: bool = False
    RERANK_MODEL: str = "BAAI/bge-reranker-large"
    
    # Hybrid Search Configuration
    USE_HYBRID_SEARCH: bool = True
    HYBRID_DENSE_WEIGHT: float = 0.5
    HYBRID_SPARSE_WEIGHT: float = 0.5
    BM25_ENABLED: bool = True

    # Cache Configuration
    CACHE_TTL: int = 3600  # seconds
    USE_SEMANTIC_CACHE: bool = True
    SEMANTIC_CACHE_THRESHOLD: float = 0.85

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = ".txt,.pdf,.docx,.md"
    DOCS_DIR: str = "data/docs"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_ENDPOINT: str = "http://localhost:4317"
    
    # Query Understanding
    USE_QUERY_CLASSIFICATION: bool = True
    USE_QUERY_REWRITING: bool = True
    USE_MULTI_QUERY: bool = False
    USE_HYDE: bool = False
    
    # Feedback & Analytics
    FEEDBACK_ENABLED: bool = True
    ANALYTICS_ENABLED: bool = True

    # WebSocket
    WEBSOCKET_ENABLED: bool = True
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30  # seconds

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Convert comma-separated string to list."""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(',')]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
