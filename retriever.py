# Updated imports
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from config import EMBEDDING_MODEL
import os

def get_retriever():
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    return db.as_retriever(search_kwargs={"k": 5})


def get_document_sources(docs) -> list:
    """Extract source information from retrieved documents."""
    sources = []
    for doc in docs:
        # Extract filename from metadata or use a default
        filename = doc.metadata.get("source", "Unknown")
        if filename:
            filename = os.path.basename(filename)

        # Extract page number if available
        page = doc.metadata.get("page", None)

        sources.append({
            "filename": filename,
            "page": page,
            "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
            "relevance_score": 1.0  # Could be calculated based on similarity score
        })

    return sources