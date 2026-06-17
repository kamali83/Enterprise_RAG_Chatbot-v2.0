"""
Query enhancement services including HyDE (Hypothetical Document Embeddings)
"""
from typing import List, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_service import get_llm_service

logger = get_logger(__name__)


class HyDEService:
    """
    HyDE (Hypothetical Document Embeddings) service for query rewriting.
    
    HyDE works by:
    1. Generating a hypothetical document that would answer the query
    2. Using the hypothetical document for retrieval instead of the original query
    3. This helps bridge the vocabulary gap between query and documents
    """
    
    def __init__(self):
        self.llm_service = None
        self._initialized = False
    
    def initialize(self):
        """Initialize the service."""
        if self._initialized:
            return
        
        self.llm_service = get_llm_service()
        self.llm_service.initialize()
        self._initialized = True
    
    async def generate_hypothetical_document(
        self,
        query: str,
        max_length: int = 200
    ) -> str:
        """
        Generate a hypothetical document that answers the query.
        
        Args:
            query: The original user query
            max_length: Maximum length of the hypothetical document
            
        Returns:
            A hypothetical document text
        """
        if not self._initialized:
            self.initialize()
        
        prompt = f"""Write a detailed document that answers the following question.
The document should be factual, comprehensive, and contain relevant information.
Question: {query}

Document:"""
        
        try:
            # Generate without context since we're creating hypothetical content
            hypothetical = await self.llm_service.generate(
                prompt=prompt,
                context="",
                provider="local"  # Use local model for cost efficiency
            )
            
            # Truncate if too long
            if len(hypothetical) > max_length:
                hypothetical = hypothetical[:max_length].rsplit(' ', 1)[0] + "..."
            
            logger.info(f"Generated hypothetical document for query: {query[:50]}...")
            return hypothetical
        
        except Exception as e:
            logger.error(f"HyDE generation failed: {e}")
            # Fallback to original query
            return query


class QueryRewriter:
    """Service for rewriting queries to improve retrieval."""
    
    def __init__(self):
        self.hyde_service = None
        self._initialized = False
    
    def initialize(self):
        """Initialize the service."""
        if self._initialized:
            return
        
        self.hyde_service = HyDEService()
        self.hyde_service.initialize()
        self._initialized = True
    
    async def rewrite_with_hyde(self, query: str) -> str:
        """
        Rewrite query using HyDE technique.
        
        Args:
            query: Original query
            
        Returns:
            Hypothetical document for embedding-based retrieval
        """
        if not self._initialized:
            self.initialize()
        
        return await self.hyde_service.generate_hypothetical_document(query)
    
    async def expand_query(
        self,
        query: str,
        num_variations: int = 3
    ) -> List[str]:
        """
        Generate query variations for better retrieval coverage.
        
        Args:
            query: Original query
            num_variations: Number of variations to generate
            
        Returns:
            List of query variations
        """
        if not self._initialized:
            self.initialize()
        
        prompt = f"""Generate {num_variations} different ways to ask the following question.
Each variation should use different vocabulary but maintain the same meaning.
Format: One variation per line.

Question: {query}

Variations:"""
        
        try:
            variations_text = await self.llm_service.generate(prompt, "")
            variations = [
                v.strip() for v in variations_text.split('\n')
                if v.strip() and v.strip() != query
            ][:num_variations]
            
            # Always include original query
            if query not in variations:
                variations.insert(0, query)
            
            logger.info(f"Generated {len(variations)} query variations")
            return variations
        
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return [query]
    
    async def rewrite_with_context(
        self,
        query: str,
        conversation_history: List[dict]
    ) -> str:
        """
        Rewrite query using conversation context for follow-up questions.
        
        Args:
            query: Current query (may be a follow-up)
            conversation_history: List of previous messages
            
        Returns:
            Contextualized query
        """
        if not conversation_history:
            return query
        
        # Build context from last 2 exchanges
        recent_history = conversation_history[-4:]  # Last 2 user-bot pairs
        
        context_parts = []
        for msg in recent_history:
            role = "User" if msg.get("sender") == "user" else "Assistant"
            content = msg.get("content", "")[:100]  # Truncate for context
            context_parts.append(f"{role}: {content}")
        
        context = "\n".join(context_parts)
        
        prompt = f"""Based on the conversation history, rewrite the following question
to be self-contained and clear without needing the context.

Conversation History:
{context}

Question: {query}

Rewritten Question:"""
        
        try:
            rewritten = await self.llm_service.generate(prompt, "")
            return rewritten.strip() if rewritten.strip() else query
        except Exception as e:
            logger.error(f"Context rewriting failed: {e}")
            return query


class RAGEnhancementService:
    """
    Enhanced RAG service with query rewriting capabilities.
    Combines retrieval with HyDE and query expansion.
    """
    
    def __init__(self):
        self.query_rewriter = QueryRewriter()
        self._initialized = False
    
    def initialize(self):
        """Initialize the service."""
        if self._initialized:
            return
        
        self.query_rewriter.initialize()
        self._initialized = True
    
    async def enhanced_retrieve(
        self,
        query: str,
        retriever_func,
        use_hyde: bool = True,
        use_expansion: bool = False,
        k: int = 5
    ):
        """
        Perform enhanced retrieval with query rewriting.
        
        Args:
            query: Original query
            retriever_func: Function to call for retrieval
            use_hyde: Whether to use HyDE for retrieval
            use_expansion: Whether to use query expansion
            k: Number of documents to retrieve
            
        Returns:
            Retrieved documents
        """
        if not self._initialized:
            self.initialize()
        
        if use_hyde:
            # Use HyDE for retrieval
            hypothetical_doc = await self.query_rewriter.rewrite_with_hyde(query)
            logger.info(f"Using HyDE for retrieval: {hypothetical_doc[:100]}...")
            docs = retriever_func(hypothetical_doc, k=k)
        elif use_expansion:
            # Use query expansion
            variations = await self.query_rewriter.expand_query(query)
            all_docs = []
            seen = set()
            
            for var in variations:
                var_docs = retriever_func(var, k=k // len(variations))
                for doc in var_docs:
                    doc_id = hash(doc.page_content)
                    if doc_id not in seen:
                        seen.add(doc_id)
                        all_docs.append(doc)
            
            docs = all_docs[:k]
            logger.info(f"Retrieved {len(docs)} unique docs from {len(variations)} variations")
        else:
            # Standard retrieval
            docs = retriever_func(query, k=k)
        
        return docs


# Global instances
hyde_service = HyDEService()
query_rewriter = QueryRewriter()
rag_enhancement = RAGEnhancementService()


def get_hyde_service():
    """Get HyDE service instance."""
    return hyde_service


def get_query_rewriter():
    """Get query rewriter instance."""
    return query_rewriter
