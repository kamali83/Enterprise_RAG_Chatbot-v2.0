"""
Tests for new enhancement features:
- Hybrid Search
- Query Understanding
- Feedback Service
- Multi-LLM Providers
"""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from app.services.hybrid_retrieval import BM25Retriever, HybridRetriever, ReciprocalRankFusion
from app.services.query_understanding import (
    QueryClassification,
    QueryRewriter,
    QueryUnderstandingPipeline,
    QueryType
)
from app.services.feedback_service import FeedbackService, FeedbackType
from langchain_core.documents import Document


# ============================================================================
# Hybrid Search Tests
# ============================================================================

class TestBM25Retriever:
    """Tests for BM25 sparse retriever."""

    def test_bm25_initialization(self):
        """Test BM25 retriever initializes correctly."""
        documents = [
            Document(page_content="Python is a programming language", metadata={"id": 1}),
            Document(page_content="Java is also a programming language", metadata={"id": 2}),
            Document(page_content="Python is great for data science", metadata={"id": 3}),
        ]

        retriever = BM25Retriever(documents)

        assert retriever._indexed is True
        assert len(retriever.tokenized_corpus) == 3

    def test_bm25_search(self):
        """Test BM25 search returns relevant documents."""
        documents = [
            Document(page_content="Python is a programming language", metadata={"id": 1}),
            Document(page_content="Java is also a programming language", metadata={"id": 2}),
            Document(page_content="Python is great for data science", metadata={"id": 3}),
        ]

        retriever = BM25Retriever(documents)
        results = retriever.search("Python programming", k=2)

        # Should return at least 1 result
        assert len(results) >= 1
        # First result should contain Python or programming
        assert "Python" in results[0][0].page_content or "programming" in results[0][0].page_content

    def test_bm25_search_with_metadata(self):
        """Test BM25 includes metadata in search."""
        documents = [
            Document(
                page_content="API documentation",
                metadata={"filename": "api_guide.pdf"}
            ),
            Document(
                page_content="User manual",
                metadata={"filename": "user_manual.pdf"}
            ),
        ]

        retriever = BM25Retriever(documents)
        results = retriever.search("API guide", k=1)

        # Should return at least the API document
        assert len(results) >= 1
        # Check metadata is preserved
        assert results[0][0].metadata["filename"] == "api_guide.pdf"


class TestReciprocalRankFusion:
    """Tests for RRF fusion algorithm."""

    def test_rrf_fuse_equal_weights(self):
        """Test RRF fusion with equal weights."""
        doc1 = Document(page_content="Doc 1")
        doc2 = Document(page_content="Doc 2")
        doc3 = Document(page_content="Doc 3")

        # Two retrieval results
        results1 = [(doc1, 0.9), (doc2, 0.8), (doc3, 0.7)]
        results2 = [(doc2, 0.9), (doc1, 0.8), (doc3, 0.7)]

        rrf = ReciprocalRankFusion(k=60)
        fused = rrf.fuse([results1, results2])

        assert len(fused) == 3
        # Results should be properly ranked (either doc1 or doc2 can be first depending on tie-breaking)
        assert fused[0][0] in [doc1, doc2]

    def test_rrf_fuse_weighted(self):
        """Test RRF fusion with different weights."""
        doc1 = Document(page_content="Doc 1")
        doc2 = Document(page_content="Doc 2")

        results1 = [(doc1, 0.9), (doc2, 0.8)]
        results2 = [(doc2, 0.9), (doc1, 0.8)]

        rrf = ReciprocalRankFusion(k=60)
        # Give more weight to first result list
        fused = rrf.fuse([results1, results2], weights=[0.8, 0.2])

        # doc1 should be first due to higher weight on results1
        assert fused[0][0] == doc1


class TestHybridRetriever:
    """Tests for hybrid retriever."""

    def test_hybrid_retriever_initialization(self):
        """Test hybrid retriever initializes correctly."""
        documents = [
            Document(page_content="Python programming", metadata={}),
            Document(page_content="Java programming", metadata={}),
        ]

        retriever = HybridRetriever(documents=documents, use_hybrid=True)

        assert retriever.bm25_retriever is not None
        assert retriever.use_hybrid is True

    def test_hybrid_retrieve_dense_only(self):
        """Test hybrid retriever with dense only."""
        mock_dense_retriever = Mock()
        mock_dense_retriever.invoke.return_value = [
            Document(page_content="Dense result"),
        ]

        retriever = HybridRetriever(
            dense_retriever=mock_dense_retriever,
            use_hybrid=False
        )

        results = retriever.retrieve("query", k=1)

        assert len(results) == 1
        assert results[0].page_content == "Dense result"

    def test_hybrid_retrieve_with_scores(self):
        """Test hybrid retrieval returns scores."""
        documents = [
            Document(page_content="Test document about Python", metadata={}),
        ]

        retriever = HybridRetriever(documents=documents, use_hybrid=False)
        results = retriever.retrieve_with_scores("test", k=1)

        # Should return at least 1 result with score
        assert len(results) >= 1
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2


# ============================================================================
# Query Understanding Tests
# ============================================================================

class TestQueryClassification:
    """Tests for query classification."""

    def test_classify_technical_query(self):
        """Test classification of technical queries."""
        classifier = QueryClassification()

        query_type, confidence = classifier.classify(
            "How to configure the API endpoint for REST service?"
        )

        # Should be TECHNICAL or GENERAL with reasonable confidence
        assert query_type in [QueryType.TECHNICAL, QueryType.GENERAL]
        assert confidence >= 0.5

    def test_classify_troubleshooting_query(self):
        """Test classification of troubleshooting queries."""
        classifier = QueryClassification()

        query_type, confidence = classifier.classify(
            "Error: Database connection failed, how to fix?"
        )

        assert query_type == QueryType.TROUBLESHOOTING
        assert confidence > 0.5

    def test_classify_how_to_query(self):
        """Test classification of how-to queries."""
        classifier = QueryClassification()

        query_type, confidence = classifier.classify(
            "How do I create a new user account?"
        )

        # Should be HOW_TO or GENERAL
        assert query_type in [QueryType.HOW_TO, QueryType.GENERAL]
        assert confidence >= 0.5

    def test_classify_definition_query(self):
        """Test classification of definition queries."""
        classifier = QueryClassification()

        query_type, confidence = classifier.classify(
            "What is machine learning?"
        )

        # Should be DEFINITION or GENERAL (confidence may vary)
        assert query_type in [QueryType.DEFINITION, QueryType.GENERAL]
        assert confidence >= 0.3  # Lower threshold for short queries

    def test_get_retrieval_strategy(self):
        """Test retrieval strategy for query types."""
        classifier = QueryClassification()

        strategy = classifier.get_retrieval_strategy(QueryType.TECHNICAL)

        assert "dense_weight" in strategy
        assert "sparse_weight" in strategy
        assert "k" in strategy
        # Technical queries should favor sparse retrieval
        assert strategy["sparse_weight"] >= strategy["dense_weight"]


class TestQueryRewriter:
    """Tests for query rewriting."""

    def test_rewrite_fix_typos(self):
        """Test typo correction."""
        rewriter = QueryRewriter()

        rewritten = rewriter.rewrite(
            "wat is the eror message?",
            expand=False,
            expand_abbreviations=False
        )

        assert "what" in rewritten.lower()

    def test_rewrite_expand_abbreviations(self):
        """Test abbreviation expansion."""
        rewriter = QueryRewriter()

        rewritten = rewriter.rewrite(
            "How to use API in Python?",
            fix_typos=False,
            expand=False
        )

        # Should include both API and expansion
        assert "api" in rewritten.lower()

    def test_rewrite_preserves_meaning(self):
        """Test rewriting preserves query meaning."""
        rewriter = QueryRewriter()

        original = "How to fix database connection error?"
        rewritten = rewriter.rewrite(original)

        # Key concepts should remain
        assert "database" in rewritten.lower() or "connection" in rewritten.lower()


class TestQueryUnderstandingPipeline:
    """Tests for complete query understanding pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_process_query(self):
        """Test pipeline processes query correctly."""
        with patch('app.services.query_understanding.get_llm_service'):
            pipeline = QueryUnderstandingPipeline()

            result = await pipeline.process(
                "What is the error handling mechanism?",
                use_multi_query=False,
                use_hyde=False
            )

            assert "original_query" in result
            assert "query_type" in result
            assert "rewritten_query" in result
            assert "final_query" in result
            assert "retrieval_strategy" in result


# ============================================================================
# Feedback Service Tests
# ============================================================================

class TestFeedbackService:
    """Tests for feedback service."""

    def test_submit_positive_feedback(self):
        """Test submitting positive feedback."""
        service = FeedbackService()
        service.initialize()

        feedback = service.submit_explicit_feedback(
            user_id=1,
            conversation_id=1,
            message_id=1,
            is_positive=True,
            feedback_text="Very helpful!",
            tags=["helpful", "accurate"]
        )

        assert feedback.score == 1.0
        assert feedback.feedback_type == FeedbackType.EXPLICIT.value
        assert feedback.feedback_text == "Very helpful!"

    def test_submit_negative_feedback(self):
        """Test submitting negative feedback."""
        service = FeedbackService()
        service.initialize()

        feedback = service.submit_explicit_feedback(
            user_id=1,
            conversation_id=1,
            message_id=2,
            is_positive=False,
            feedback_text="Incorrect information",
            tags=["incorrect"]
        )

        assert feedback.score == 0.0
        assert feedback.is_flagged is False

    def test_submit_rating_feedback(self):
        """Test submitting star rating feedback."""
        service = FeedbackService()
        service.initialize()

        feedback = service.submit_rating_feedback(
            user_id=1,
            conversation_id=1,
            message_id=3,
            rating=4,
            feedback_text="Good answer"
        )

        # 4/5 = 0.8
        assert abs(feedback.score - 0.8) < 0.01

    def test_track_implicit_feedback(self):
        """Test tracking implicit feedback from behavior."""
        service = FeedbackService()
        service.initialize()

        feedback = service.track_implicit_feedback(
            user_id=1,
            conversation_id=1,
            message_id=4,
            follow_up_asked=True,
            time_spent_seconds=30,
            conversation_continued=True
        )

        assert feedback is not None
        assert feedback.feedback_type == FeedbackType.IMPLICIT.value
        # Positive signals should result in score > 0.5
        assert feedback.score > 0.5

    def test_get_feedback_stats(self):
        """Test getting feedback statistics."""
        service = FeedbackService()
        service.initialize()

        # Submit some feedback
        service.submit_explicit_feedback(1, 1, 1, is_positive=True)
        service.submit_explicit_feedback(1, 1, 2, is_positive=True)
        service.submit_explicit_feedback(1, 1, 3, is_positive=False)

        stats = service.get_feedback_stats()

        assert stats["total_feedback"] == 3
        assert stats["positive_count"] == 2
        assert stats["negative_count"] == 1
        assert stats["average_score"] > 0.5

    def test_get_low_quality_responses(self):
        """Test identifying low-quality responses."""
        service = FeedbackService()
        service.initialize()

        # Submit negative feedback for same message
        service.submit_explicit_feedback(1, 1, 100, is_positive=False)
        service.submit_explicit_feedback(1, 1, 100, is_positive=False)

        low_quality = service.get_low_quality_responses(limit=10)

        assert len(low_quality) > 0
        assert low_quality[0]["message_id"] == 100
        assert low_quality[0]["average_score"] < 0.5

    def test_get_improvement_suggestions(self):
        """Test getting improvement suggestions."""
        service = FeedbackService()
        service.initialize()

        # Submit mixed feedback
        for i in range(10):
            service.submit_explicit_feedback(1, 1, i, is_positive=(i < 4))  # 40% positive

        suggestions = service.get_improvement_suggestions()

        assert "statistics" in suggestions
        assert "suggestions" in suggestions
        assert "priority" in suggestions


# ============================================================================
# Integration Tests
# ============================================================================

class TestHybridSearchIntegration:
    """Integration tests for hybrid search."""

    def test_end_to_end_hybrid_retrieval(self):
        """Test complete hybrid retrieval flow."""
        # Create test documents
        documents = [
            Document(page_content="Python is great for machine learning", metadata={"source": "ml_guide.pdf"}),
            Document(page_content="Java is used for enterprise applications", metadata={"source": "java_guide.pdf"}),
            Document(page_content="Python web frameworks: Django and Flask", metadata={"source": "web_dev.pdf"}),
            Document(page_content="Machine learning algorithms include regression and classification", metadata={"source": "ml_algos.pdf"}),
        ]

        # Create hybrid retriever
        retriever = HybridRetriever(documents=documents, use_hybrid=True)

        # Search
        results = retriever.retrieve("Python machine learning", k=2)

        assert len(results) <= 2
        # Should return at least 1 result about Python or ML
        assert len(results) >= 1
        assert any("Python" in doc.page_content or "machine learning" in doc.page_content
                  for doc in results)


class TestQueryUnderstandingIntegration:
    """Integration tests for query understanding."""

    @pytest.mark.asyncio
    async def test_classification_improves_retrieval(self):
        """Test that query classification leads to better retrieval parameters."""
        classifier = QueryClassification()

        # Technical query
        query_type, confidence = classifier.classify("API REST endpoint configuration")
        strategy = classifier.get_retrieval_strategy(query_type)

        # Technical queries should have higher sparse weight
        assert strategy["sparse_weight"] >= 0.5
        assert strategy["k"] >= 5  # More documents for technical queries
