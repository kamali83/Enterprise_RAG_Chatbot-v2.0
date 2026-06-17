"""
Document service for ingestion and vector store management
"""
import os
from typing import List
from langchain_community.document_loaders import UnstructuredFileLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from app.core.config import settings
from app.core.logging import get_logger
from app.services.rag_service import get_rag_service

logger = get_logger(__name__)

DOCS_DIR = settings.DOCS_DIR
FAISS_INDEX_PATH = "faiss_index"


def load_documents() -> List[Document]:
    """Load all documents from the docs directory."""
    docs = []
    
    if not os.path.exists(DOCS_DIR):
        logger.warning(f"Documents directory not found: {DOCS_DIR}")
        return docs
    
    for file in os.listdir(DOCS_DIR):
        # Skip hidden files, cache directories, and non-document files
        if file.startswith('.') or file == '__pycache__' or os.path.isdir(os.path.join(DOCS_DIR, file)):
            continue
            
        file_path = os.path.join(DOCS_DIR, file)
        ext = os.path.splitext(file)[1].lower()
        
        try:
            if ext == ".txt":
                loader = UnstructuredFileLoader(file_path)
                file_docs = loader.load()
            elif ext == ".pdf":
                loader = PyPDFLoader(file_path)
                file_docs = loader.load()
            elif ext == ".docx":
                from langchain_community.document_loaders import Docx2txtLoader
                loader = Docx2txtLoader(file_path)
                file_docs = loader.load()
            elif ext == ".md":
                from langchain_community.document_loaders import UnstructuredMarkdownLoader
                loader = UnstructuredMarkdownLoader(file_path)
                file_docs = loader.load()
            else:
                continue  # Skip unsupported file types
            
            # Add filename to metadata
            for doc in file_docs:
                doc.metadata["source"] = file_path
            
            docs.extend(file_docs)
            logger.info(f"Loaded document: {file}")
        
        except Exception as e:
            logger.error(f"Failed to load {file}: {e}")
    
    return docs


def create_vector_store(documents: List[Document] = None):
    """Create or update the vector store."""
    logger.info("Creating vector store")
    
    # Load documents if not provided
    if documents is None:
        documents = load_documents()
    
    if not documents:
        logger.warning("No documents to index")
        return
    
    # Split documents into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)
    
    logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
    
    # Get embeddings from RAG service
    rag_service = get_rag_service()
    rag_service.initialize()
    embeddings = rag_service.embeddings
    
    # Create vector store
    vector_store = FAISS.from_documents(chunks, embeddings)
    
    # Save vector store
    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
    vector_store.save_local(FAISS_INDEX_PATH)
    
    logger.info(f"Vector store saved to {FAISS_INDEX_PATH}")


async def reindex_documents():
    """Reindex all documents (async wrapper)."""
    # Run in thread pool to avoid blocking
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, create_vector_store)
    logger.info("Reindexing complete")


def get_document_stats() -> dict:
    """Get statistics about indexed documents."""
    if not os.path.exists(DOCS_DIR):
        return {
            "total_documents": 0,
            "total_size_bytes": 0,
            "indexed": False,
        }
    
    total_docs = 0
    total_size = 0
    
    for file in os.listdir(DOCS_DIR):
        file_path = os.path.join(DOCS_DIR, file)
        if os.path.isfile(file_path):
            total_docs += 1
            total_size += os.path.getsize(file_path)
    
    return {
        "total_documents": total_docs,
        "total_size_bytes": total_size,
        "indexed": os.path.exists(os.path.join(FAISS_INDEX_PATH, "index.faiss")),
    }
