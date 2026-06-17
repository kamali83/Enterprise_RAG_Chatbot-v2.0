# config.py

# Embeddings
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# LLM Model (Free Hugging Face)
MODEL_NAME = "google/flan-t5-large"

# Database
DATABASE_URL = "sqlite:///./rag_saas.db"

# JWT
SECRET_KEY = "supersecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# RAG Configuration
CHUNK_SIZE = 800  # Slightly smaller for better focus
CHUNK_OVERLAP = 150  # More overlap for better context continuity
RETRIEVAL_K = 8  # Retrieve more documents for better coverage