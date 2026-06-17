"""
Hybrid Search Module - Combines dense (embedding) and sparse (BM25) retrieval
with Reciprocal Rank Fusion (RRF) for optimal results.
"""
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import re
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BM25Retriever:
    """Sparse retriever using BM25 algorithm for keyword-based search."""

    def __init__(self, documents: List[Document]):
        """
        Initialize BM25 retriever.

        Args:
            documents: List of documents to index
        """
        self.documents = documents
        self.tokenized_corpus = []
        self._indexed = False

        self._index_documents()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        # Simple tokenization: lowercase and split on non-alphanumeric
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _index_documents(self):
        """Index all documents for BM25 retrieval."""
        logger.info(f"Indexing {len(self.documents)} documents for BM25 retrieval")

        for doc in self.documents:
            # Combine page content with metadata for better retrieval
            text = doc.page_content
            filename = doc.metadata.get('filename', '')
            if filename:
                text = f"{filename} {text}"

            tokens = self._tokenize(text)
            self.tokenized_corpus.append(tokens)

        self.bm25 = BM25Okapi(self.tokenized_corpus)
        self._indexed = True
        logger.info("BM25 indexing complete")

    def search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """
        Search for documents using BM25.

        Args:
            query: Search query
            k: Number of documents to retrieve

        Returns:
            List of (document, score) tuples
        """
        if not self._indexed:
            logger.warning("BM25 retriever not indexed")
            return []

        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        # Get top k documents with scores
        doc_scores = []
        for i, score in enumerate(scores):
            # Use absolute score or small positive value for ranking
            # BM25 can return negative scores on small corpora
            adjusted_score = max(0.01, abs(score))
            doc_scores.append((self.documents[i], float(adjusted_score)))

        # Sort by score descending
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        return doc_scores[:k]

    def add_documents(self, documents: List[Document]):
        """Add new documents and reindex."""
        self.documents.extend(documents)
        self._index_documents()


class ReciprocalRankFusion:
    """
    Reciprocal Rank Fusion (RRF) for combining multiple retrieval results.

    RRF formula: score = 1 / (k + rank)
    where k is a constant (typically 60) and rank is the position in results.
    """

    def __init__(self, k: int = 60):
        """
        Initialize RRF.

        Args:
            k: Ranking constant
        """
        self.k = k

    def fuse(
        self,
        result_lists: List[List[Tuple[Document, float]]],
        weights: Optional[List[float]] = None
    ) -> List[Tuple[Document, float]]:
        """
        Fuse multiple retrieval results using RRF.

        Args:
            result_lists: List of retrieval results (each is list of (doc, score) tuples)
            weights: Optional weights for each result list

        Returns:
            Fused and ranked list of (document, fused_score) tuples
        """
        if not result_lists:
            return []

        # Normalize weights
        if weights is None:
            weights = [1.0] * len(result_lists)

        # Calculate RRF scores for each document
        doc_scores: Dict[int, float] = {}
        doc_map: Dict[int, Document] = {}

        for result_list, weight in zip(result_lists, weights):
            for rank, (doc, score) in enumerate(result_list):
                doc_id = id(doc)
                if doc_id not in doc_map:
                    doc_map[doc_id] = doc
                    doc_scores[doc_id] = 0.0

                # RRF score: weight / (k + rank)
                rrf_score = weight / (self.k + rank + 1)
                doc_scores[doc_id] += rrf_score

        # Sort by fused score
        fused_results = [
            (doc_map[doc_id], score)
            for doc_id, score in doc_scores.items()
        ]
        fused_results.sort(key=lambda x: x[1], reverse=True)

        return fused_results


class HybridRetriever:
    """
    Hybrid retriever combining dense (embedding) and sparse (BM25) retrieval.

    Supports:
    - Dense retrieval only
    - Sparse retrieval only
    - Hybrid retrieval with RRF fusion
    - Adaptive weighting based on query type
    """

    def __init__(
        self,
        dense_retriever=None,
        documents: Optional[List[Document]] = None,
        use_hybrid: bool = True,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5
    ):
        """
        Initialize hybrid retriever.

        Args:
            dense_retriever: LangChain retriever for dense retrieval
            documents: List of documents for BM25 indexing
            use_hybrid: Whether to use hybrid retrieval
            dense_weight: Weight for dense retrieval in fusion
            sparse_weight: Weight for sparse retrieval in fusion
        """
        self.dense_retriever = dense_retriever
        self.use_hybrid = use_hybrid
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

        # Initialize BM25 retriever if documents provided
        self.bm25_retriever = None
        if documents:
            self.bm25_retriever = BM25Retriever(documents)

        self.rrf = ReciprocalRankFusion(k=60)

        logger.info(
            f"HybridRetriever initialized - hybrid: {use_hybrid}, "
            f"dense_weight: {dense_weight}, sparse_weight: {sparse_weight}"
        )

    def set_documents(self, documents: List[Document]):
        """Set documents for BM25 indexing."""
        self.bm25_retriever = BM25Retriever(documents)

    def retrieve(
        self,
        query: str,
        k: int = 5,
        use_hybrid: Optional[bool] = None
    ) -> List[Document]:
        """
        Retrieve documents using hybrid search.

        Args:
            query: Search query
            k: Number of documents to retrieve
            use_hybrid: Override default hybrid setting

        Returns:
            List of retrieved documents
        """
        use_hybrid = use_hybrid if use_hybrid is not None else self.use_hybrid

        dense_results = []
        sparse_results = []

        # Dense retrieval
        if self.dense_retriever:
            try:
                dense_docs = self.dense_retriever.invoke(query)
                # Convert to (doc, score) format - use rank as score for dense
                dense_results = [(doc, 1.0 / (i + 1)) for i, doc in enumerate(dense_docs[:k*2])]
                logger.debug(f"Dense retrieval: {len(dense_results)} documents")
            except Exception as e:
                logger.error(f"Dense retrieval error: {e}")

        # Sparse retrieval (BM25)
        if self.bm25_retriever:
            try:
                sparse_results = self.bm25_retriever.search(query, k=k*2)
                logger.debug(f"Sparse retrieval: {len(sparse_results)} documents")
            except Exception as e:
                logger.error(f"Sparse retrieval error: {e}")

        # Return based on retrieval mode
        if not dense_results and not sparse_results:
            return []

        if not use_hybrid or not (dense_results and sparse_results):
            # Return best of dense or sparse
            if dense_results:
                return [doc for doc, score in dense_results[:k]]
            elif sparse_results:
                return [doc for doc, score in sparse_results[:k]]
            return []

        # Hybrid fusion with RRF
        fused_results = self.rrf.fuse(
            [dense_results, sparse_results],
            weights=[self.dense_weight, self.sparse_weight]
        )

        logger.info(f"Hybrid retrieval: {len(fused_results)} documents after fusion")

        return [doc for doc, score in fused_results[:k]]

    def retrieve_with_scores(
        self,
        query: str,
        k: int = 5,
        use_hybrid: Optional[bool] = None
    ) -> List[Tuple[Document, float]]:
        """
        Retrieve documents with scores.

        Args:
            query: Search query
            k: Number of documents to retrieve
            use_hybrid: Override default hybrid setting

        Returns:
            List of (document, score) tuples
        """
        use_hybrid = use_hybrid if use_hybrid is not None else self.use_hybrid

        dense_results = []
        sparse_results = []

        if self.dense_retriever:
            try:
                dense_docs = self.dense_retriever.invoke(query)
                dense_results = [(doc, 1.0 / (i + 1)) for i, doc in enumerate(dense_docs[:k*2])]
            except Exception as e:
                logger.error(f"Dense retrieval error: {e}")

        if self.bm25_retriever:
            try:
                sparse_results = self.bm25_retriever.search(query, k=k*2)
            except Exception as e:
                logger.error(f"Sparse retrieval error: {e}")

        if not dense_results and not sparse_results:
            return []

        if not use_hybrid or not (dense_results and sparse_results):
            if dense_results:
                return dense_results[:k]
            elif sparse_results:
                return sparse_results[:k]
            return []

        fused_results = self.rrf.fuse(
            [dense_results, sparse_results],
            weights=[self.dense_weight, self.sparse_weight]
        )

        return fused_results[:k]


class AdaptiveHybridRetriever(HybridRetriever):
    """
    Adaptive hybrid retriever that adjusts weights based on query characteristics.

    Automatically increases sparse weight for:
    - Queries with technical terms
    - Queries with acronyms
    - Queries with numbers/codes

    Increases dense weight for:
    - Conceptual questions
    - Semantic queries
    """

    def __init__(
        self,
        dense_retriever=None,
        documents: Optional[List[Document]] = None,
        base_dense_weight: float = 0.5,
        base_sparse_weight: float = 0.5
    ):
        super().__init__(
            dense_retriever=dense_retriever,
            documents=documents,
            use_hybrid=True,
            dense_weight=base_dense_weight,
            sparse_weight=base_sparse_weight
        )
        self.base_dense_weight = base_dense_weight
        self.base_sparse_weight = base_sparse_weight

    def _analyze_query(self, query: str) -> Dict[str, float]:
        """
        Analyze query to determine optimal weights.

        Returns:
            Dict with suggested dense_weight and sparse_weight
        """
        sparse_boost = 0.0

        # Check for technical terms (uppercase with numbers, e.g., "API", "RAG")
        technical_terms = len(re.findall(r'\b[A-Z]{2,}\b', query))
        sparse_boost += min(technical_terms * 0.1, 0.3)

        # Check for acronyms
        acronyms = len(re.findall(r'\b[A-Z][A-Z]+\b', query))
        sparse_boost += min(acronyms * 0.05, 0.2)

        # Check for code/numbers
        has_codes = bool(re.search(r'\b\w+\d+\w*\b', query))
        if has_codes:
            sparse_boost += 0.15

        # Check for question words (semantic queries)
        question_words = bool(re.search(r'\b(what|how|why|when|where|who|which)\b', query.lower()))
        if question_words:
            sparse_boost -= 0.1  # Prefer dense for semantic queries

        # Calculate final weights
        sparse_boost = max(-0.2, min(0.4, sparse_boost))  # Clamp between -0.2 and 0.4

        dense_weight = self.base_dense_weight - sparse_boost / 2
        sparse_weight = self.base_sparse_weight + sparse_boost / 2

        # Normalize to sum to 1
        total = dense_weight + sparse_weight
        dense_weight /= total
        sparse_weight /= total

        logger.debug(
            f"Query analysis: dense_weight={dense_weight:.2f}, sparse_weight={sparse_weight:.2f}"
        )

        return {
            "dense_weight": dense_weight,
            "sparse_weight": sparse_weight
        }

    def retrieve(
        self,
        query: str,
        k: int = 5,
        use_hybrid: Optional[bool] = None
    ) -> List[Document]:
        """Retrieve with adaptive weights."""
        use_hybrid = use_hybrid if use_hybrid is not None else self.use_hybrid

        if use_hybrid:
            # Adjust weights based on query
            weights = self._analyze_query(query)
            self.dense_weight = weights["dense_weight"]
            self.sparse_weight = weights["sparse_weight"]

        return super().retrieve(query, k=k, use_hybrid=use_hybrid)
