from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from config import (
    EMBEDDING_PROVIDER, LLM_PROVIDER,
    OPENAI_API_KEY, OPENAI_MODEL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    GOOGLE_API_KEY, GOOGLE_MODEL,
    OLLAMA_BASE_URL, OLLAMA_LLM_MODEL, OLLAMA_EMBED_MODEL
)

def get_embeddings():
    if EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    elif EMBEDDING_PROVIDER == "ollama":
        return OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=OLLAMA_EMBED_MODEL)
    elif EMBEDDING_PROVIDER == "google":
        return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=GOOGLE_API_KEY)
    elif EMBEDDING_PROVIDER == "huggingface":
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    else:
        raise ValueError(f"Unsupported embedding provider: {EMBEDDING_PROVIDER}")

def get_llm():
    if LLM_PROVIDER == "openai":
        return ChatOpenAI(model_name=OPENAI_MODEL, openai_api_key=OPENAI_API_KEY, temperature=0)
    elif LLM_PROVIDER == "anthropic":
        return ChatAnthropic(model_name=ANTHROPIC_MODEL, anthropic_api_key=ANTHROPIC_API_KEY, temperature=0)
    elif LLM_PROVIDER == "google":
        return ChatGoogleGenerativeAI(model=GOOGLE_MODEL, google_api_key=GOOGLE_API_KEY, temperature=0)
    elif LLM_PROVIDER == "ollama":
        return ChatOllama(base_url=OLLAMA_BASE_URL, model=OLLAMA_LLM_MODEL, temperature=0)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")
