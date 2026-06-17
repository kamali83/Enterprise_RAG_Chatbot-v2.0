"""
Query Understanding Pipeline

Enhances retrieval quality through:
1. Query Classification - Route to specialized retrievers
2. Query Rewriting - Fix typos, expand abbreviations, resolve coreferences
3. Multi-Query Generation - Generate variations for better coverage
4. HyDE - Hypothetical Document Embeddings
"""
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import re
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_service import get_llm_service

logger = get_logger(__name__)


class QueryType(Enum):
    """Types of queries for classification."""
    GENERAL = "general"
    TECHNICAL = "technical"
    TROUBLESHOOTING = "troubleshooting"
    HOW_TO = "how_to"
    DEFINITION = "definition"
    COMPARISON = "comparison"
    CODE = "code"
    NUMERICAL = "numerical"


class QueryClassification:
    """
    Classifies queries to optimize retrieval strategy.
    
    Different query types benefit from different:
    - Retrieval weights (dense vs sparse)
    - Context building strategies
    - Generation parameters
    """

    # Keywords for each query type
    TECHNICAL_KEYWORDS = {
        'api', 'sdk', 'library', 'framework', 'database', 'server', 'client',
        'http', 'rest', 'graphql', 'sql', 'nosql', 'kubernetes', 'docker',
        'microservice', 'architecture', 'deployment', 'infrastructure'
    }

    TROUBLESHOOTING_KEYWORDS = {
        'error', 'bug', 'issue', 'problem', 'fail', 'failed', 'exception',
        'crash', 'broken', 'not working', 'wrong', 'fix', 'debug', 'troubleshoot'
    }

    HOW_TO_KEYWORDS = {
        'how to', 'how do i', 'how can i', 'steps to', 'guide to', 'tutorial',
        'walkthrough', 'implement', 'create', 'build', 'setup', 'configure'
    }

    DEFINITION_KEYWORDS = {
        'what is', 'what are', 'define', 'definition', 'meaning', 'explain',
        'describe', 'overview', 'introduction to', 'understand'
    }

    COMPARISON_KEYWORDS = {
        'vs', 'versus', 'compare', 'comparison', 'difference', 'better',
        'which one', 'choose between', 'prefer'
    }

    CODE_KEYWORDS = {
        'code', 'example', 'snippet', 'function', 'method', 'class', 'module',
        'script', 'program', 'implementation', 'sample'
    }

    def classify(self, query: str) -> Tuple[QueryType, float]:
        """
        Classify a query into a type with confidence score.

        Args:
            query: User query

        Returns:
            Tuple of (QueryType, confidence_score)
        """
        query_lower = query.lower()

        scores = {
            QueryType.TECHNICAL: 0.0,
            QueryType.TROUBLESHOOTING: 0.0,
            QueryType.HOW_TO: 0.0,
            QueryType.DEFINITION: 0.0,
            QueryType.COMPARISON: 0.0,
            QueryType.CODE: 0.0,
            QueryType.NUMERICAL: 0.0,
            QueryType.GENERAL: 0.3,  # Default baseline (lowered)
        }

        # Check for technical keywords
        for keyword in self.TECHNICAL_KEYWORDS:
            if keyword in query_lower:
                scores[QueryType.TECHNICAL] += 0.15

        # Check for troubleshooting keywords
        for keyword in self.TROUBLESHOOTING_KEYWORDS:
            if keyword in query_lower:
                scores[QueryType.TROUBLESHOOTING] += 0.2

        # Check for how-to patterns
        for keyword in self.HOW_TO_KEYWORDS:
            if keyword in query_lower:
                scores[QueryType.HOW_TO] += 0.25  # Increased weight

        # Check for definition patterns
        for keyword in self.DEFINITION_KEYWORDS:
            if keyword in query_lower:
                scores[QueryType.DEFINITION] += 0.25  # Increased weight

        # Check for comparison patterns
        for keyword in self.COMPARISON_KEYWORDS:
            if keyword in query_lower:
                scores[QueryType.COMPARISON] += 0.2

        # Check for code-related patterns
        for keyword in self.CODE_KEYWORDS:
            if keyword in query_lower:
                scores[QueryType.CODE] += 0.15

        # Check for numerical queries (contain numbers)
        if re.search(r'\d+', query):
            scores[QueryType.NUMERICAL] += 0.3

        # Check for technical terms (uppercase acronyms)
        acronyms = re.findall(r'\b[A-Z]{2,}\b', query)
        if acronyms:
            scores[QueryType.TECHNICAL] += len(acronyms) * 0.1

        # Check for code snippets (backticks, special chars)
        if re.search(r'[`{}()\[\].;]', query):
            scores[QueryType.CODE] += 0.2

        # Find best match
        best_type = max(scores.keys(), key=lambda k: scores[k])
        confidence = min(scores[best_type], 1.0)

        # Normalize confidence if it's the best match but low
        if confidence < 0.5 and best_type != QueryType.GENERAL:
            confidence = 0.51  # Just above threshold

        logger.debug(f"Query classified as {best_type.value} with confidence {confidence:.2f}")

        return best_type, confidence

    def get_retrieval_strategy(self, query_type: QueryType) -> Dict[str, Any]:
        """
        Get optimal retrieval strategy for query type.

        Returns:
            Dict with retrieval parameters
        """
        strategies = {
            QueryType.GENERAL: {
                "dense_weight": 0.6,
                "sparse_weight": 0.4,
                "k": 5,
                "use_reranking": False
            },
            QueryType.TECHNICAL: {
                "dense_weight": 0.4,
                "sparse_weight": 0.6,  # More weight on keywords
                "k": 8,
                "use_reranking": True
            },
            QueryType.TROUBLESHOOTING: {
                "dense_weight": 0.5,
                "sparse_weight": 0.5,
                "k": 10,  # Retrieve more for context
                "use_reranking": True
            },
            QueryType.HOW_TO: {
                "dense_weight": 0.6,
                "sparse_weight": 0.4,
                "k": 7,
                "use_reranking": False
            },
            QueryType.DEFINITION: {
                "dense_weight": 0.7,
                "sparse_weight": 0.3,  # More semantic
                "k": 3,  # Fewer, focused results
                "use_reranking": False
            },
            QueryType.COMPARISON: {
                "dense_weight": 0.5,
                "sparse_weight": 0.5,
                "k": 8,
                "use_reranking": True
            },
            QueryType.CODE: {
                "dense_weight": 0.3,
                "sparse_weight": 0.7,  # Exact matches important
                "k": 5,
                "use_reranking": False
            },
            QueryType.NUMERICAL: {
                "dense_weight": 0.4,
                "sparse_weight": 0.6,
                "k": 5,
                "use_reranking": False
            }
        }

        return strategies.get(query_type, strategies[QueryType.GENERAL])


class QueryRewriter:
    """
    Rewrites queries to improve retrieval quality.

    Techniques:
    - Spelling correction
    - Abbreviation expansion
    - Query expansion with synonyms
    - Coreference resolution
    - Grammar normalization
    """

    # Common abbreviations in enterprise context
    ABBREVIATIONS = {
        "api": "application programming interface",
        "ui": "user interface",
        "ux": "user experience",
        "db": "database",
        "sql": "structured query language",
        "nosql": "not only sql",
        "http": "hypertext transfer protocol",
        "rest": "representational state transfer",
        "json": "javascript object notation",
        "xml": "extensible markup language",
        "css": "cascading style sheets",
        "html": "hypertext markup language",
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "ml": "machine learning",
        "dl": "deep learning",
        "nlp": "natural language processing",
        "rag": "retrieval augmented generation",
        "llm": "large language model",
        "ai": "artificial intelligence",
        "etl": "extract transform load",
        "ci": "continuous integration",
        "cd": "continuous deployment",
        "devops": "development operations",
        "k8s": "kubernetes",
        "aws": "amazon web services",
        "azure": "microsoft azure",
        "gcp": "google cloud platform",
    }

    # Common typos and corrections
    TYPOS = {
        "wat": "what",
        "wht": "what",
        "hw": "how",
        "wih": "with",
        "tht": "that",
        "hte": "the",
        "adn": "and",
        "fro": "from",
        "wro": "wrong",
        "eror": "error",
        "bug": "bug",
        "issus": "issue",
        "probelm": "problem",
        "questoin": "question",
        "asnwer": "answer",
    }

    def __init__(self, llm_service=None):
        """
        Initialize query rewriter.

        Args:
            llm_service: LLM service for advanced rewriting
        """
        self.llm_service = llm_service or get_llm_service()

    def rewrite(
        self,
        query: str,
        expand: bool = True,
        fix_typos: bool = True,
        expand_abbreviations: bool = True
    ) -> str:
        """
        Rewrite query to improve retrieval.

        Args:
            query: Original query
            expand: Whether to expand with synonyms
            fix_typos: Whether to fix common typos
            expand_abbreviations: Whether to expand abbreviations

        Returns:
            Rewritten query
        """
        rewritten = query

        # Fix typos
        if fix_typos:
            rewritten = self._fix_typos(rewritten)

        # Expand abbreviations
        if expand_abbreviations:
            rewritten = self._expand_abbreviations(rewritten)

        # Expand with synonyms
        if expand:
            rewritten = self._expand_query(rewritten)

        logger.debug(f"Query rewritten: '{query}' -> '{rewritten}'")

        return rewritten

    def _fix_typos(self, query: str) -> str:
        """Fix common typos."""
        words = query.lower().split()
        corrected = []

        for word in words:
            # Remove punctuation for lookup
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.TYPOS:
                corrected.append(self.TYPOS[clean_word])
            else:
                corrected.append(word)

        return ' '.join(corrected)

    def _expand_abbreviations(self, query: str) -> str:
        """Expand common abbreviations."""
        words = query.lower().split()
        expanded = []

        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.ABBREVIATIONS:
                # Add both abbreviation and expansion for better retrieval
                expanded.append(f"{clean_word} ({self.ABBREVIATIONS[clean_word]})")
            else:
                expanded.append(word)

        return ' '.join(expanded)

    def _expand_query(self, query: str) -> str:
        """Add synonyms and related terms."""
        # Simple expansion - can be enhanced with synonym dictionaries
        expansions = {
            "error": "error exception bug issue problem",
            "fast": "fast quick rapid speedy efficient",
            "slow": "slow sluggish delayed performance",
            "good": "good better best excellent quality",
            "bad": "bad poor wrong incorrect issue",
            "use": "use utilize employ apply",
            "create": "create build make generate",
            "help": "help guide assist support",
        }

        query_lower = query.lower()
        additions = []

        for key, value in expansions.items():
            if key in query_lower:
                additions.append(value)

        if additions:
            return f"{query} {' '.join(additions)}"

        return query

    async def rewrite_with_llm(self, query: str) -> List[str]:
        """
        Use LLM to generate query variations.

        Args:
            query: Original query

        Returns:
            List of rewritten queries
        """
        prompt = f"""Rewrite the following query in 3 different ways to improve search results.
Keep the same meaning but use different words and phrasings.

Original query: {query}

Rewritten queries (one per line):"""

        try:
            response = await self.llm_service.generate(prompt, "")
            variations = [line.strip() for line in response.split('\n') if line.strip()]
            return variations[:3]
        except Exception as e:
            logger.error(f"LLM query rewriting failed: {e}")
            return [query]


class MultiQueryGenerator:
    """
    Generates multiple query variations for comprehensive retrieval.

    Benefits:
    - Better coverage of relevant documents
    - Reduces impact of poor query formulation
    - Improves recall
    """

    def __init__(self, llm_service=None):
        """
        Initialize multi-query generator.

        Args:
            llm_service: LLM service for generation
        """
        self.llm_service = llm_service or get_llm_service()
        self.rewriter = QueryRewriter(self.llm_service)

    async def generate(self, query: str, num_variations: int = 3) -> List[str]:
        """
        Generate multiple query variations.

        Args:
            query: Original query
            num_variations: Number of variations to generate

        Returns:
            List of query variations
        """
        variations = [query]

        # Add rule-based variations
        rewritten = self.rewriter.rewrite(query)
        if rewritten != query:
            variations.append(rewritten)

        # Add LLM-based variations
        try:
            llm_variations = await self.rewriter.rewrite_with_llm(query)
            variations.extend(llm_variations[:num_variations - len(variations)])
        except Exception as e:
            logger.warning(f"LLM variations failed: {e}")

        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v.lower() not in seen:
                seen.add(v.lower())
                unique_variations.append(v)

        logger.info(f"Generated {len(unique_variations)} query variations")

        return unique_variations[:num_variations]


class HyDEGenerator:
    """
    Hypothetical Document Embeddings (HyDE) generator.

    HyDE works by:
    1. Generate a hypothetical document that answers the query
    2. Use the hypothetical document for retrieval (instead of query)
    3. The hypothetical document has better semantic similarity with relevant docs

    Paper: https://arxiv.org/abs/2212.10496
    """

    def __init__(self, llm_service=None):
        """
        Initialize HyDE generator.

        Args:
            llm_service: LLM service for generation
        """
        self.llm_service = llm_service or get_llm_service()

    async def generate_hypothetical_document(self, query: str) -> str:
        """
        Generate a hypothetical document that answers the query.

        Args:
            query: User query

        Returns:
            Hypothetical document text
        """
        prompt = f"""Please write a hypothetical document that would answer the following query.
The document should be factual-sounding and contain relevant information.
Write about 3-5 sentences.

Query: {query}

Hypothetical Document:"""

        try:
            response = await self.llm_service.generate(prompt, "")
            logger.debug(f"Generated hypothetical document: {len(response)} chars")
            return response
        except Exception as e:
            logger.error(f"HyDE generation failed: {e}")
            return query  # Fallback to original query


class QueryUnderstandingPipeline:
    """
    Complete query understanding pipeline.

    Pipeline stages:
    1. Classification → Determine query type
    2. Rewriting → Fix typos, expand abbreviations
    3. Multi-query → Generate variations (optional)
    4. HyDE → Generate hypothetical document (optional)

    Usage:
        pipeline = QueryUnderstandingPipeline()
        result = await pipeline.process(query)
        docs = retriever.retrieve(result["final_query"])
    """

    def __init__(self, llm_service=None):
        """
        Initialize query understanding pipeline.

        Args:
            llm_service: LLM service
        """
        self.llm_service = llm_service or get_llm_service()
        self.classifier = QueryClassification()
        self.rewriter = QueryRewriter(self.llm_service)
        self.multi_query_generator = MultiQueryGenerator(self.llm_service)
        self.hyde_generator = HyDEGenerator(self.llm_service)

    async def process(
        self,
        query: str,
        use_multi_query: bool = False,
        use_hyde: bool = False,
        rewrite: bool = True
    ) -> Dict[str, Any]:
        """
        Process query through the understanding pipeline.

        Args:
            query: Original query
            use_multi_query: Generate multiple query variations
            use_hyde: Use HyDE for retrieval
            rewrite: Apply query rewriting

        Returns:
            Dict with:
            - original_query: Original query
            - query_type: Classified type
            - confidence: Classification confidence
            - rewritten_query: Rewritten query
            - final_query: Query to use for retrieval
            - variations: List of query variations (if multi-query)
            - hypothetical_document: Hypothetical doc (if HyDE)
            - retrieval_strategy: Recommended retrieval parameters
        """
        result = {
            "original_query": query,
            "variations": [query],
            "hypothetical_document": None
        }

        # Stage 1: Classification
        query_type, confidence = self.classifier.classify(query)
        result["query_type"] = query_type
        result["confidence"] = confidence
        result["retrieval_strategy"] = self.classifier.get_retrieval_strategy(query_type)

        logger.info(f"Query classified as {query_type.value} (confidence: {confidence:.2f})")

        # Stage 2: Rewriting
        if rewrite:
            rewritten = self.rewriter.rewrite(query)
            result["rewritten_query"] = rewritten
        else:
            result["rewritten_query"] = query

        # Stage 3: Multi-query or HyDE
        if use_multi_query:
            variations = await self.multi_query_generator.generate(query)
            result["variations"] = variations
            result["final_query"] = variations[0]  # Use first for retrieval
            logger.info(f"Generated {len(variations)} query variations")

        elif use_hyde:
            hypothetical = await self.hyde_generator.generate_hypothetical_document(query)
            result["hypothetical_document"] = hypothetical
            result["final_query"] = hypothetical  # Use hypothetical for retrieval
            logger.info("Generated hypothetical document for HyDE")

        else:
            result["final_query"] = result["rewritten_query"]

        return result


# Global pipeline instance
query_understanding_pipeline = QueryUnderstandingPipeline()


def get_query_understanding_pipeline() -> QueryUnderstandingPipeline:
    """Get the query understanding pipeline instance."""
    return query_understanding_pipeline
