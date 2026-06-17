from pydantic import BaseModel
from typing import List, Optional

class QueryRequest(BaseModel):
    prompt: str

class SourceDocument(BaseModel):
    filename: str
    page: Optional[int] = None
    content: str
    relevance_score: float = 1.0

class QueryResponse(BaseModel):
    answer: str
    sources: Optional[List[SourceDocument]] = None

class IngestResponse(BaseModel):
    status: str
    message: str
