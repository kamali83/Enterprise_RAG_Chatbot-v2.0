import os
import json
from typing import List
# Updated imports
from langchain_community.document_loaders import (
    UnstructuredFileLoader, 
    PyPDFLoader, 
    Docx2txtLoader,
    TextLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from config import EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP

def load_documents() -> List[Document]:
    """Load all documents from data/docs directory."""
    docs = []
    docs_dir = "data/docs"
    
    if not os.path.exists(docs_dir):
        print(f"Warning: {docs_dir} directory not found")
        return docs
    
    for file in os.listdir(docs_dir):
        if file.startswith('.'):
            continue
            
        file_path = os.path.join(docs_dir, file)
        ext = os.path.splitext(file)[1].lower()
        
        try:
            if ext == ".txt":
                loader = TextLoader(file_path, encoding='utf-8')
                file_docs = loader.load()
            elif ext == ".pdf":
                loader = PyPDFLoader(file_path)
                file_docs = loader.load()
            elif ext in [".docx", ".doc"]:
                loader = Docx2txtLoader(file_path)
                file_docs = loader.load()
            elif ext == ".md":
                loader = TextLoader(file_path, encoding='utf-8')
                file_docs = loader.load()
            else:
                print(f"Skipping unsupported file type: {file}")
                continue
            
            # Add filename and path to metadata
            for doc in file_docs:
                doc.metadata["source"] = file_path
                doc.metadata["filename"] = file
            docs.extend(file_docs)
            print(f"✓ Loaded: {file} ({len(file_docs)} pages/sections)")
            
        except Exception as e:
            print(f"✗ Error loading {file}: {e}")
    
    print(f"\nTotal documents loaded: {len(docs)}")
    return docs

def create_vector_store():
    """Create and save FAISS vector store."""
    print("=" * 60)
    print("Starting document ingestion...")
    print("=" * 60)
    
    # Load documents
    documents = load_documents()
    
    if not documents:
        print("No documents found to index!")
        return
    
    # Split documents into chunks
    print(f"\nSplitting documents into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks")
    
    # Create embeddings
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )
    
    # Create vector store
    print("Creating FAISS vector store...")
    vector_store = FAISS.from_documents(chunks, embeddings)
    
    # Save locally
    print("Saving vector store to faiss_index/...")
    vector_store.save_local("faiss_index")
    
    print("\n" + "=" * 60)
    print("✅ Ingestion complete!")
    print(f"   - Documents: {len(documents)}")
    print(f"   - Chunks: {len(chunks)}")
    print(f"   - Index saved to: faiss_index/")
    print("=" * 60)

if __name__ == "__main__":
    create_vector_store()