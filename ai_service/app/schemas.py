from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


ImpactLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
PriorityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ReplyTone = Literal["empathetic", "update", "resolved"]


class FeedbackInput(BaseModel):
    id: int
    code: str = ""
    title: str
    content: str
    impact_level: ImpactLevel = "MEDIUM"
    votes_count: int = 0
    sender_email: str = ""
    sender_name: str = ""
    source_code: str = "WEB_FORM"
    submitted_at: Optional[str] = None


class AnalyzeRequest(BaseModel):
    feedbacks: list[FeedbackInput] = Field(default_factory=list)
    similarity_threshold: float = Field(default=0.72, ge=0.40, le=0.99)
    eps: float = Field(default=0.48, ge=0.05, le=0.95)
    min_samples: int = Field(default=2, ge=2, le=20)
    use_llm: bool = True
    total_inbox_count: Optional[int] = None


class EmbeddingResult(BaseModel):
    feedback_id: int
    normalized_text: str
    embedding: list[float]
    embedding_model: str


class SimilarityPair(BaseModel):
    feedback_a_id: int
    feedback_b_id: int
    similarity_score: float
    is_exact_normalized_match: bool = False


class ClusterMember(BaseModel):
    feedback_id: int
    similarity_to_centroid: float


class ClusterOutput(BaseModel):
    cluster_index: int
    title: str
    summary: str
    possible_causes: list[str]
    user_impact: str
    ai_recommendations: list[str]
    draft_customer_reply: str
    analysis_mode: str
    ai_confidence: float
    volume_score: float
    impact_score: float
    severity_score: float
    priority_score: float
    priority_level: PriorityLevel
    priority_reasoning: str
    affected_customers_count: int
    members: list[ClusterMember]


class AnalyzeResponse(BaseModel):
    embedding_model: str
    analysis_mode: str
    embeddings: list[EmbeddingResult]
    duplicate_candidates: list[SimilarityPair]
    clusters: list[ClusterOutput]
    unassigned_feedback_ids: list[int]
    stats: dict[str, Any]


class EmbedRequest(BaseModel):
    items: list[FeedbackInput]
    use_llm: bool = True


class EmbedResponse(BaseModel):
    embedding_model: str
    embeddings: list[EmbeddingResult]


class SimilaritySearchRequest(BaseModel):
    target: FeedbackInput
    candidates: list[FeedbackInput]
    top_k: int = Field(default=5, ge=1, le=50)
    min_similarity: float = Field(default=0.35, ge=0.0, le=1.0)
    use_llm: bool = True


class SimilaritySearchMatch(BaseModel):
    feedback_id: int
    code: str
    title: str
    similarity_score: float
    is_exact_normalized_match: bool


class SimilaritySearchResponse(BaseModel):
    embedding_model: str
    matches: list[SimilaritySearchMatch]


class SummarizeClusterRequest(BaseModel):
    feedbacks: list[FeedbackInput]
    total_inbox_count: Optional[int] = None
    use_llm: bool = True
    custom_title: Optional[str] = None


class SummarizeClusterResponse(BaseModel):
    title: str
    summary: str
    possible_causes: list[str]
    user_impact: str
    ai_recommendations: list[str]
    draft_customer_reply: str
    analysis_mode: str
    ai_confidence: float
    volume_score: float
    impact_score: float
    severity_score: float
    priority_score: float
    priority_level: PriorityLevel
    priority_reasoning: str
    affected_customers_count: int


class DraftReplyRequest(BaseModel):
    insight_title: str
    insight_summary: str
    sample_feedbacks: list[str] = Field(default_factory=list)
    tone: ReplyTone = "empathetic"
    use_llm: bool = True


class DraftReplyResponse(BaseModel):
    draft_reply: str
    analysis_mode: str
    tone: ReplyTone
