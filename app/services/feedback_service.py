"""
Feedback Service - Track answer quality and user satisfaction

Features:
- Explicit feedback (thumbs up/down, ratings)
- Implicit feedback (follow-up questions, session duration)
- Feedback analytics and reporting
- Active learning flags for model improvement
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from enum import Enum
import json
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class FeedbackType(Enum):
    """Types of feedback."""
    EXPLICIT = "explicit"  # Thumbs up/down, ratings
    IMPLICIT = "implicit"  # Follow-up questions, session time


class FeedbackSource(Enum):
    """Sources of feedback."""
    USER = "user"
    SYSTEM = "system"
    ANALYTICS = "analytics"


# Feedback database model
class FeedbackEntry:
    """Feedback entry model (SQLAlchemy-like for SQLite compatibility)."""

    def __init__(
        self,
        user_id: int,
        conversation_id: int,
        message_id: int,
        feedback_type: str,
        feedback_source: str,
        score: float,
        feedback_text: Optional[str] = None,
        metadata: Optional[Dict] = None,
        is_flagged: bool = False,
        created_at: Optional[datetime] = None
    ):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.feedback_type = feedback_type
        self.feedback_source = feedback_source
        self.score = score  # 0.0 to 1.0
        self.feedback_text = feedback_text
        self.metadata = metadata or {}
        self.is_flagged = is_flagged
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": getattr(self, 'id', None),
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "feedback_type": self.feedback_type,
            "feedback_source": self.feedback_source,
            "score": self.score,
            "feedback_text": self.feedback_text,
            "metadata": self.metadata,
            "is_flagged": self.is_flagged,
            "created_at": str(self.created_at)
        }


class FeedbackService:
    """
    Service for managing user feedback on AI responses.

    Collects and analyzes feedback to:
    - Track answer quality over time
    - Identify problematic queries
    - Enable active learning
    - Improve RAG pipeline
    """

    def __init__(self):
        self._initialized = False
        self.feedback_cache: Dict[int, List[FeedbackEntry]] = {}

    def initialize(self):
        """Initialize feedback service."""
        if self._initialized:
            return

        logger.info("Feedback service initialized")
        self._initialized = True

    def _get_db(self) -> Session:
        """Get database session."""
        return next(get_db())

    def submit_explicit_feedback(
        self,
        user_id: int,
        conversation_id: int,
        message_id: int,
        is_positive: bool,
        feedback_text: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> FeedbackEntry:
        """
        Submit explicit feedback (thumbs up/down).

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message_id: Message ID
            is_positive: True for thumbs up, False for thumbs down
            feedback_text: Optional detailed feedback
            tags: Optional tags (e.g., ["incorrect", "outdated", "helpful"])

        Returns:
            FeedbackEntry created
        """
        if not self._initialized:
            self.initialize()

        score = 1.0 if is_positive else 0.0

        metadata = {
            "tags": tags or [],
            "feedback_method": "explicit"
        }

        feedback = FeedbackEntry(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            feedback_type=FeedbackType.EXPLICIT.value,
            feedback_source=FeedbackSource.USER.value,
            score=score,
            feedback_text=feedback_text,
            metadata=metadata
        )

        # Store in database
        try:
            db = self._get_db()
            # For now, store in cache (can be extended to use DB table)
            if conversation_id not in self.feedback_cache:
                self.feedback_cache[conversation_id] = []
            self.feedback_cache[conversation_id].append(feedback)

            logger.info(
                f"Explicit feedback received: {'positive' if is_positive else 'negative'} "
                f"for message {message_id}"
            )
        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")

        return feedback

    def submit_rating_feedback(
        self,
        user_id: int,
        conversation_id: int,
        message_id: int,
        rating: int,  # 1-5 stars
        feedback_text: Optional[str] = None
    ) -> FeedbackEntry:
        """
        Submit star rating feedback.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message_id: Message ID
            rating: 1-5 star rating
            feedback_text: Optional comment

        Returns:
            FeedbackEntry created
        """
        if not self._initialized:
            self.initialize()

        # Normalize rating to 0-1 scale
        score = rating / 5.0

        metadata = {
            "rating": rating,
            "feedback_method": "rating"
        }

        feedback = FeedbackEntry(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            feedback_type=FeedbackType.EXPLICIT.value,
            feedback_source=FeedbackSource.USER.value,
            score=score,
            feedback_text=feedback_text,
            metadata=metadata
        )

        # Store
        try:
            if conversation_id not in self.feedback_cache:
                self.feedback_cache[conversation_id] = []
            self.feedback_cache[conversation_id].append(feedback)

            logger.info(f"Rating feedback received: {rating}/5 for message {message_id}")
        except Exception as e:
            logger.error(f"Failed to store rating feedback: {e}")

        return feedback

    def track_implicit_feedback(
        self,
        user_id: int,
        conversation_id: int,
        message_id: int,
        follow_up_asked: bool = False,
        time_spent_seconds: Optional[int] = None,
        conversation_continued: bool = False,
        query_reformulated: bool = False
    ) -> Optional[FeedbackEntry]:
        """
        Track implicit feedback from user behavior.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message_id: Message ID
            follow_up_asked: User asked a follow-up question
            time_spent_seconds: Time spent reading response
            conversation_continued: User continued the conversation
            query_reformulated: User reformulated and asked again

        Returns:
            FeedbackEntry if significant, None otherwise
        """
        if not self._initialized:
            self.initialize()

        # Calculate implicit score based on signals
        signals = []

        # Follow-up question indicates engagement (positive)
        if follow_up_asked:
            signals.append(0.3)

        # Time spent (optimal range: 10-60 seconds)
        if time_spent_seconds:
            if 10 <= time_spent_seconds <= 60:
                signals.append(0.3)  # Good engagement
            elif time_spent_seconds < 5:
                signals.append(-0.2)  # Too fast, likely rejected
            elif time_spent_seconds > 120:
                signals.append(-0.1)  # Too long, likely confused

        # Conversation continued (positive)
        if conversation_continued:
            signals.append(0.2)

        # Query reformulated (negative - first answer wasn't good)
        if query_reformulated:
            signals.append(-0.3)

        if not signals:
            return None

        # Calculate final score
        avg_score = sum(signals) / len(signals)
        score = max(0.0, min(1.0, 0.5 + avg_score))  # Center around 0.5

        metadata = {
            "follow_up_asked": follow_up_asked,
            "time_spent_seconds": time_spent_seconds,
            "conversation_continued": conversation_continued,
            "query_reformulated": query_reformulated,
            "signals": signals,
            "feedback_method": "implicit"
        }

        feedback = FeedbackEntry(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            feedback_type=FeedbackType.IMPLICIT.value,
            feedback_source=FeedbackSource.SYSTEM.value,
            score=score,
            metadata=metadata
        )

        # Store
        try:
            if conversation_id not in self.feedback_cache:
                self.feedback_cache[conversation_id] = []
            self.feedback_cache[conversation_id].append(feedback)

            logger.debug(f"Implicit feedback tracked: score={score:.2f}")
        except Exception as e:
            logger.error(f"Failed to store implicit feedback: {e}")

        return feedback

    def flag_for_review(
        self,
        feedback_id: int,
        reason: str,
        priority: str = "medium"
    ):
        """
        Flag feedback entry for manual review.

        Args:
            feedback_id: Feedback entry ID
            reason: Reason for flagging
            priority: low, medium, high
        """
        logger.info(f"Feedback {feedback_id} flagged for review: {reason} (priority: {priority})")
        # Implementation: Update database flag

    def get_feedback_stats(
        self,
        conversation_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get feedback statistics.

        Args:
            conversation_id: Filter by conversation
            user_id: Filter by user
            start_date: Start date for range
            end_date: End date for range

        Returns:
            Dict with statistics
        """
        # Collect feedback entries
        all_feedback = []
        for conv_id, feedback_list in self.feedback_cache.items():
            if conversation_id and conv_id != conversation_id:
                continue
            all_feedback.extend(feedback_list)

        if user_id:
            all_feedback = [f for f in all_feedback if f.user_id == user_id]

        if start_date:
            all_feedback = [f for f in all_feedback if f.created_at >= start_date]

        if end_date:
            all_feedback = [f for f in all_feedback if f.created_at <= end_date]

        if not all_feedback:
            return {
                "total_feedback": 0,
                "average_score": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "explicit_count": 0,
                "implicit_count": 0
            }

        # Calculate statistics
        total = len(all_feedback)
        avg_score = sum(f.score for f in all_feedback) / total
        positive_count = sum(1 for f in all_feedback if f.score >= 0.7)
        negative_count = sum(1 for f in all_feedback if f.score < 0.4)
        explicit_count = sum(1 for f in all_feedback if f.feedback_type == FeedbackType.EXPLICIT.value)
        implicit_count = sum(1 for f in all_feedback if f.feedback_type == FeedbackType.IMPLICIT.value)

        # Flagged for review
        flagged_count = sum(1 for f in all_feedback if f.is_flagged)

        # Score distribution
        score_distribution = {
            "5_star": sum(1 for f in all_feedback if f.score >= 0.9),
            "4_star": sum(1 for f in all_feedback if 0.7 <= f.score < 0.9),
            "3_star": sum(1 for f in all_feedback if 0.4 <= f.score < 0.7),
            "2_star": sum(1 for f in all_feedback if 0.2 <= f.score < 0.4),
            "1_star": sum(1 for f in all_feedback if f.score < 0.2)
        }

        return {
            "total_feedback": total,
            "average_score": round(avg_score, 3),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "explicit_count": explicit_count,
            "implicit_count": implicit_count,
            "flagged_count": flagged_count,
            "score_distribution": score_distribution,
            "satisfaction_rate": round(positive_count / total * 100, 1) if total > 0 else 0.0
        }

    def get_low_quality_responses(
        self,
        limit: int = 20,
        min_feedback_count: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get responses with consistently low feedback.

        Args:
            limit: Maximum number to return
            min_feedback_count: Minimum feedback count to consider

        Returns:
            List of low-quality response records
        """
        # Group by message
        message_feedback: Dict[int, List[FeedbackEntry]] = {}

        for feedback_list in self.feedback_cache.values():
            for feedback in feedback_list:
                if feedback.message_id not in message_feedback:
                    message_feedback[feedback.message_id] = []
                message_feedback[feedback.message_id].append(feedback)

        # Find low-quality messages
        low_quality = []
        for message_id, feedbacks in message_feedback.items():
            if len(feedbacks) < min_feedback_count:
                continue

            avg_score = sum(f.score for f in feedbacks) / len(feedbacks)
            if avg_score < 0.5:  # Below threshold
                low_quality.append({
                    "message_id": message_id,
                    "average_score": round(avg_score, 3),
                    "feedback_count": len(feedbacks),
                    "conversation_id": feedbacks[0].conversation_id,
                    "user_id": feedbacks[0].user_id,
                    "feedback_texts": [f.feedback_text for f in feedbacks if f.feedback_text]
                })

        # Sort by score ascending
        low_quality.sort(key=lambda x: x["average_score"])

        return low_quality[:limit]

    def get_improvement_suggestions(self) -> Dict[str, Any]:
        """
        Analyze feedback to suggest improvements.

        Returns:
            Dict with improvement suggestions
        """
        stats = self.get_feedback_stats()

        suggestions = []

        # Check overall satisfaction
        if stats["satisfaction_rate"] < 70:
            suggestions.append({
                "area": "Overall Quality",
                "issue": f"Satisfaction rate is {stats['satisfaction_rate']}%",
                "recommendation": "Review RAG pipeline, consider better retrieval or LLM"
            })

        # Check negative feedback ratio
        if stats["negative_count"] > stats["positive_count"] * 0.5:
            suggestions.append({
                "area": "Negative Feedback",
                "issue": "High ratio of negative feedback",
                "recommendation": "Analyze low-quality responses for common patterns"
            })

        # Check implicit vs explicit gap
        explicit_feedback = [f for f in self.feedback_cache.values() for f in f
                           if f.feedback_type == FeedbackType.EXPLICIT.value]
        implicit_feedback = [f for f in self.feedback_cache.values() for f in f
                           if f.feedback_type == FeedbackType.IMPLICIT.value]

        if explicit_feedback and implicit_feedback:
            explicit_avg = sum(f.score for f in explicit_feedback) / len(explicit_feedback)
            implicit_avg = sum(f.score for f in implicit_feedback) / len(implicit_feedback)

            if abs(explicit_avg - implicit_avg) > 0.2:
                suggestions.append({
                    "area": "Feedback Discrepancy",
                    "issue": "Gap between explicit and implicit feedback",
                    "recommendation": "Users may be rating kindly but not actually satisfied"
                })

        return {
            "statistics": stats,
            "suggestions": suggestions,
            "priority": "high" if len(suggestions) > 2 else "medium" if suggestions else "low"
        }


# Global feedback service instance
feedback_service = FeedbackService()


def get_feedback_service() -> FeedbackService:
    """Get the feedback service instance."""
    return feedback_service
