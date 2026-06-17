"""
RAG (Retrieval-Augmented Generation) service
"""
from typing import List, Dict, Any, Optional
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_service import get_llm_service
import os

logger = get_logger(__name__)


class RAGService:
    """Service for RAG operations including retrieval and generation."""
    
    def __init__(self):
        self.embeddings = None
        self.vector_store = None
        self.llm_service = None
        self._initialized = False
    
    def initialize(self):
        """Initialize embeddings and load vector store."""
        if self._initialized:
            return
        
        logger.info("Initializing RAG service")
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        
        # Load vector store
        if os.path.exists("faiss_index"):
            try:
                self.vector_store = FAISS.load_local(
                    "faiss_index",
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Vector store loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load vector store: {e}")
                self.vector_store = None
        else:
            logger.warning("No vector store found at faiss_index")
            self.vector_store = None
        
        # Initialize LLM service
        self.llm_service = get_llm_service()
        self.llm_service.initialize()
        
        self._initialized = True
    
    def retrieve(self, query: str, k: Optional[int] = None) -> List[Document]:
        """Retrieve relevant documents for a query using similarity search."""
        if not self._initialized:
            self.initialize()

        if not self.vector_store:
            logger.warning("Vector store not available")
            return []

        k = k or settings.RETRIEVAL_K

        try:
            # Use similarity search with score threshold
            docs_and_scores = self.vector_store.similarity_search_with_score(query, k=k*2)
            
            # Filter by score threshold (optional - removes very irrelevant docs)
            filtered_docs = []
            for doc, score in docs_and_scores:
                # Score is distance (lower is better), typically < 1.0 is good
                if score < 1.5:  # Adjust threshold as needed
                    filtered_docs.append(doc)
                    logger.debug(f"Doc score: {score:.4f} - {doc.metadata.get('filename', 'unknown')}")
            
            # Return top k after filtering
            result_docs = filtered_docs[:k]
            logger.info(f"Retrieved {len(result_docs)} relevant documents for query")
            return result_docs
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []
    
    async def generate_answer(self, query: str, context: str) -> str:
        """Generate an answer given a query and context."""
        if not self._initialized:
            self.initialize()

        # Log context length for debugging
        logger.info(f"Generating answer - Context length: {len(context)} chars, Query length: {len(query)} chars")
        
        return await self.llm_service.generate(query, context)
    
    async def generate_answer_stream(
        self,
        query: str,
        context: str
    ):
        """Generate a streaming answer."""
        if not self._initialized:
            self.initialize()
        
        async for token in self.llm_service.generate_stream(query, context):
            yield token
    
    async def query(self, query: str, use_reranking: bool = False) -> Dict[str, Any]:
        """
        Complete RAG query: retrieve documents and generate answer.

        Returns:
            dict with answer, sources, and metadata
        """
        # Retrieve documents
        docs = self.retrieve(query)

        if not docs:
            return {
                "answer": "I don't have enough information to answer that question. Please upload relevant documents.",
                "sources": [],
                "metadata": {"retrieved_count": 0}
            }

        # Build context from retrieved documents WITH metadata
        context_parts = []
        for i, doc in enumerate(docs):
            filename = doc.metadata.get('filename', 'Unknown')
            page = doc.metadata.get('page', '')
            header = f"[Source: {filename}" + (f", Page: {page}" if page else "") + "]"
            context_parts.append(f"{header}\n{doc.page_content}")
        
        context = "\n\n".join(context_parts)
        
        logger.info(f"Retrieved {len(docs)} documents, context built: {len(context)} chars")

        # Optional reranking
        if use_reranking and settings.USE_RERANKING:
            docs = await self._rerank_documents(query, docs)

        # Extract sources
        sources = self._extract_sources(docs)

        # Generate answer
        answer = await self.generate_answer(query, context)
        
        logger.info(f"Answer generated: {len(answer)} chars")

        return {
            "answer": answer,
            "sources": sources,
            "metadata": {
                "retrieved_count": len(docs),
                "context_length": len(context),
                "reranked": use_reranking and settings.USE_RERANKING
            }
        }
    
    def _extract_sources(self, docs: List[Document]) -> List[Dict[str, Any]]:
        """Extract source information from documents."""
        sources = []
        for i, doc in enumerate(docs):
            filename = doc.metadata.get("source", "Unknown")
            if filename:
                filename = os.path.basename(filename)

            page = doc.metadata.get("page")
            if page is not None:
                page = int(page) if isinstance(page, str) else page

            content = doc.page_content
            if len(content) > 300:
                content = content[:300] + "..."

            sources.append({
                "filename": filename,
                "page": page,
                "content": content,
                "relevance_score": round(1.0 - (i * 0.1), 2)  # Decreasing score by rank
            })

        return sources
    
    async def _rerank_documents(
        self,
        query: str,
        docs: List[Document]
    ) -> List[Document]:
        """Rerank documents using a reranking model."""
        if not settings.USE_RERANKING:
            return docs
        
        try:
            from sentence_transformers import CrossEncoder
            
            logger.info("Reranking documents")
            
            cross_encoder = CrossEncoder(settings.RERANK_MODEL)
            
            pairs = [[query, doc.page_content] for doc in docs]
            scores = cross_encoder.predict(pairs)
            
            # Sort documents by score
            scored_docs = list(zip(docs, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            return [doc for doc, score in scored_docs]
        
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return docs
    
    def get_document_sources(self) -> List[Dict[str, Any]]:
        """Get list of all document sources in the vector store."""
        if not self.vector_store:
            return []
        
        try:
            # Get all document IDs and metadata
            sources = []
            seen_files = set()
            
            for doc_id in range(len(self.vector_store.docstore._id_to_node)):
                try:
                    doc = self.vector_store.docstore.search(str(doc_id))
                    if doc and hasattr(doc, 'metadata'):
                        filename = doc.metadata.get("source", "Unknown")
                        if filename and filename not in seen_files:
                            seen_files.add(filename)
                            sources.append({
                                "filename": os.path.basename(filename),
                                "path": filename
                            })
                except Exception:
                    continue
            
            return sources
        except Exception as e:
            logger.error(f"Error getting document sources: {e}")
            return []


# Global RAG service instance
rag_service = RAGService()


def get_rag_service() -> RAGService:
    """Get the RAG service instance."""
    return rag_service
