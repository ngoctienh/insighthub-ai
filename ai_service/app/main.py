import logging
import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status

from .clustering import (
    cluster_feedbacks_dbscan,
    cosine_similarity_matrix,
    find_duplicate_candidates,
)
from .embeddings import generate_embeddings
from .preprocessing import (
    exact_normalized_hash,
    is_empty_feedback,
    normalize_for_embedding,
)
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ClusterOutput,
    DraftReplyRequest,
    DraftReplyResponse,
    EmbedRequest,
    EmbedResponse,
    EmbeddingResult,
    SimilaritySearchMatch,
    SimilaritySearchRequest,
    SimilaritySearchResponse,
    SummarizeClusterRequest,
    SummarizeClusterResponse,
)
from .scoring import calculate_priority_score
from .summarization import generate_draft_reply, summarize_cluster

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("insighthub.ai_service")

app = FastAPI(
    title="InsightHub AI Engine",
    description="Embedding, Cosine Similarity, DBSCAN Clustering, Summarization & Priority Scoring API",
    version="1.0.0",
)


def verify_internal_api_key(x_api_key: Optional[str] = Header(default=None)):
    expected = os.getenv("AI_SERVICE_API_KEY", "").strip()
    if expected and expected != "change-this-internal-service-secret":
        if x_api_key != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid AI service API key.",
            )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "insighthub-ai-service",
        "provider": os.getenv("AI_PROVIDER", "auto"),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
    }


@app.post("/embed", response_model=EmbedResponse, dependencies=[Depends(verify_internal_api_key)])
def embed_feedbacks(payload: EmbedRequest):
    if not payload.items:
        return EmbedResponse(embedding_model="none", embeddings=[])

    normalized_texts = [normalize_for_embedding(item.title, item.content) for item in payload.items]
    vectors, model_name = generate_embeddings(normalized_texts, use_llm=payload.use_llm)

    results = [
        EmbeddingResult(
            feedback_id=item.id,
            normalized_text=normalized_texts[idx],
            embedding=[round(float(x), 6) for x in vectors[idx].tolist()],
            embedding_model=model_name,
        )
        for idx, item in enumerate(payload.items)
    ]
    return EmbedResponse(embedding_model=model_name, embeddings=results)


@app.post("/similarity/search", response_model=SimilaritySearchResponse, dependencies=[Depends(verify_internal_api_key)])
def similarity_search(payload: SimilaritySearchRequest):
    if not payload.candidates:
        return SimilaritySearchResponse(embedding_model="none", matches=[])

    all_items = [payload.target] + payload.candidates
    normalized_texts = [normalize_for_embedding(it.title, it.content) for it in all_items]
    hashes = [exact_normalized_hash(txt) for txt in normalized_texts]

    vectors, model_name = generate_embeddings(normalized_texts, use_llm=payload.use_llm)
    sim_matrix = cosine_similarity_matrix(vectors)

    target_hash = hashes[0]
    matches: list[SimilaritySearchMatch] = []
    for idx, candidate in enumerate(payload.candidates, start=1):
        if candidate.id == payload.target.id:
            continue
        score = float(sim_matrix[0, idx])
        exact = hashes[idx] == target_hash
        final_score = max(score, 1.0 if exact else score)
        if exact or final_score >= payload.min_similarity:
            matches.append(
                SimilaritySearchMatch(
                    feedback_id=candidate.id,
                    code=candidate.code,
                    title=candidate.title,
                    similarity_score=round(final_score, 4),
                    is_exact_normalized_match=exact,
                )
            )

    matches.sort(key=lambda m: m.similarity_score, reverse=True)
    return SimilaritySearchResponse(
        embedding_model=model_name,
        matches=matches[: payload.top_k],
    )


@app.post("/summarize", response_model=SummarizeClusterResponse, dependencies=[Depends(verify_internal_api_key)])
def summarize_single_cluster(payload: SummarizeClusterRequest):
    summary_data = summarize_cluster(
        payload.feedbacks,
        use_llm=payload.use_llm,
        custom_title=payload.custom_title,
    )
    score_data = calculate_priority_score(
        payload.feedbacks,
        total_inbox_count=payload.total_inbox_count,
    )
    return SummarizeClusterResponse(**summary_data, **score_data)


@app.post("/draft-reply", response_model=DraftReplyResponse, dependencies=[Depends(verify_internal_api_key)])
def create_draft_reply(payload: DraftReplyRequest):
    text, mode = generate_draft_reply(
        insight_title=payload.insight_title,
        insight_summary=payload.insight_summary,
        sample_feedbacks=payload.sample_feedbacks,
        tone=payload.tone,
        use_llm=payload.use_llm,
    )
    return DraftReplyResponse(draft_reply=text, analysis_mode=mode, tone=payload.tone)


@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(verify_internal_api_key)])
def analyze_feedbacks(payload: AnalyzeRequest):
    started = time.perf_counter()

    valid_items = [
        fb for fb in payload.feedbacks if not is_empty_feedback(fb.title, fb.content)
    ]
    skipped_empty = len(payload.feedbacks) - len(valid_items)

    if not valid_items:
        return AnalyzeResponse(
            embedding_model="none",
            analysis_mode="local_nlp",
            embeddings=[],
            duplicate_candidates=[],
            clusters=[],
            unassigned_feedback_ids=[],
            stats={
                "input_count": len(payload.feedbacks),
                "processed_count": 0,
                "skipped_empty": skipped_empty,
                "clusters_count": 0,
                "duplicate_candidates_count": 0,
                "unassigned_count": 0,
                "duration_ms": 0,
            },
        )

    normalized_texts = [normalize_for_embedding(fb.title, fb.content) for fb in valid_items]
    hashes = [exact_normalized_hash(txt) for txt in normalized_texts]

    vectors, embedding_model = generate_embeddings(normalized_texts, use_llm=payload.use_llm)
    sim_matrix = cosine_similarity_matrix(vectors)

    duplicate_candidates = find_duplicate_candidates(
        feedbacks=valid_items,
        sim_matrix=sim_matrix,
        text_hashes=hashes,
        threshold=payload.similarity_threshold,
    )

    raw_clusters, unassigned_ids = cluster_feedbacks_dbscan(
        feedbacks=valid_items,
        vectors=vectors,
        sim_matrix=sim_matrix,
        eps=payload.eps,
        min_samples=payload.min_samples,
    )

    total_inbox = payload.total_inbox_count or len(valid_items)
    clusters_out: list[ClusterOutput] = []
    analysis_modes: set[str] = set()

    for raw_cluster in raw_clusters:
        member_feedbacks = [valid_items[idx] for idx in raw_cluster["member_indices"]]
        rep_ids = [m.feedback_id for m in raw_cluster["members"]]

        summary_data = summarize_cluster(
            member_feedbacks,
            representative_ids=rep_ids,
            use_llm=payload.use_llm,
        )
        score_data = calculate_priority_score(
            member_feedbacks,
            total_inbox_count=total_inbox,
        )
        analysis_modes.add(summary_data["analysis_mode"])

        clusters_out.append(
            ClusterOutput(
                cluster_index=raw_cluster["cluster_index"],
                members=raw_cluster["members"],
                **summary_data,
                **score_data,
            )
        )

    clusters_out.sort(key=lambda c: c.priority_score, reverse=True)
    for idx, cluster in enumerate(clusters_out):
        cluster.cluster_index = idx

    embedding_results = [
        EmbeddingResult(
            feedback_id=fb.id,
            normalized_text=normalized_texts[idx],
            embedding=[round(float(x), 6) for x in vectors[idx].tolist()],
            embedding_model=embedding_model,
        )
        for idx, fb in enumerate(valid_items)
    ]

    duration_ms = int((time.perf_counter() - started) * 1000)
    overall_mode = (
        next(iter(analysis_modes))
        if len(analysis_modes) == 1
        else ("mixed" if analysis_modes else "local_nlp")
    )

    return AnalyzeResponse(
        embedding_model=embedding_model,
        analysis_mode=overall_mode,
        embeddings=embedding_results,
        duplicate_candidates=duplicate_candidates,
        clusters=clusters_out,
        unassigned_feedback_ids=unassigned_ids,
        stats={
            "input_count": len(payload.feedbacks),
            "processed_count": len(valid_items),
            "skipped_empty": skipped_empty,
            "clusters_count": len(clusters_out),
            "duplicate_candidates_count": len(duplicate_candidates),
            "unassigned_count": len(unassigned_ids),
            "duration_ms": duration_ms,
        },
    )
