import logging
from typing import Any

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.feedbacks.models import Feedback
from apps.notifications.models import ActivityLog
from apps.notifications.services import log_activity
from .models import AIAnalysisJob, InsightFeedback, InsightGroup

logger = logging.getLogger(__name__)


def _ai_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.AI_SERVICE_API_KEY:
        headers["X-API-Key"] = settings.AI_SERVICE_API_KEY
    return headers


def serialize_feedback_for_ai(feedback: Feedback) -> dict[str, Any]:
    return {
        "id": feedback.id,
        "code": feedback.code,
        "title": feedback.title,
        "content": feedback.content,
        "impact_level": feedback.impact_level,
        "votes_count": feedback.votes.count(),
        "sender_email": feedback.sender_email,
        "sender_name": feedback.sender_name,
        "source_code": feedback.source.code,
        "submitted_at": feedback.submitted_at.isoformat() if feedback.submitted_at else None,
    }


def classify_priority_level(score: float) -> str:
    if score >= 80:
        return InsightGroup.PRIORITY_CRITICAL
    if score >= 60:
        return InsightGroup.PRIORITY_HIGH
    if score >= 40:
        return InsightGroup.PRIORITY_MEDIUM
    return InsightGroup.PRIORITY_LOW


def execute_ai_pipeline(job_id: int) -> AIAnalysisJob:
    job = AIAnalysisJob.objects.select_related("product", "triggered_by").get(id=job_id)
    job.status = AIAnalysisJob.STATUS_RUNNING
    job.save(update_fields=["status"])

    config = job.config or {}
    similarity_threshold = float(config.get("similarity_threshold", 0.72))
    eps = float(config.get("eps", 0.48))
    min_samples = int(config.get("min_samples", 2))
    use_llm = bool(config.get("use_llm", True))
    include_clustered = bool(config.get("include_clustered", False))

    try:
        fb_qs = Feedback.objects.select_related("source", "product").filter(
            is_duplicate_confirmed=False
        )
        if job.product_id:
            fb_qs = fb_qs.filter(product_id=job.product_id)

        total_inbox_count = fb_qs.count()

        if include_clustered:
            confirmed_fb_ids = set(
                InsightFeedback.objects.filter(
                    insight_group__verification_status=InsightGroup.VERIFY_CONFIRMED
                ).values_list("feedback_id", flat=True)
            )
            target_feedbacks = list(fb_qs.exclude(id__in=confirmed_fb_ids))
        else:
            already_grouped_ids = set(
                InsightFeedback.objects.exclude(
                    insight_group__verification_status=InsightGroup.VERIFY_REJECTED
                ).values_list("feedback_id", flat=True)
            )
            target_feedbacks = list(fb_qs.exclude(id__in=already_grouped_ids))

        if not target_feedbacks:
            job.status = AIAnalysisJob.STATUS_COMPLETED
            job.metrics = {
                "input_count": 0,
                "processed_count": 0,
                "clusters_count": 0,
                "duplicate_candidates_count": 0,
                "unassigned_count": 0,
                "message": "Không có feedback mới chưa phân nhóm để phân tích.",
            }
            job.completed_at = timezone.now()
            job.save()
            return job

        ai_payload = {
            "feedbacks": [serialize_feedback_for_ai(fb) for fb in target_feedbacks],
            "similarity_threshold": similarity_threshold,
            "eps": eps,
            "min_samples": min_samples,
            "use_llm": use_llm,
            "total_inbox_count": total_inbox_count,
        }

        with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
            resp = client.post(
                f"{settings.AI_SERVICE_URL}/analyze",
                json=ai_payload,
                headers=_ai_headers(),
            )
            resp.raise_for_status()
            ai_result = resp.json()

        fb_by_id = {fb.id: fb for fb in target_feedbacks}

        with transaction.atomic():
            if include_clustered:
                pending_qs = InsightGroup.objects.filter(
                    verification_status=InsightGroup.VERIFY_PENDING
                )
                if job.product_id:
                    pending_qs = pending_qs.filter(product_id=job.product_id)
                pending_qs.delete()

            # Save embeddings & normalized text
            for emb in ai_result.get("embeddings", []):
                fb = fb_by_id.get(emb["feedback_id"])
                if fb:
                    fb.normalized_content = emb["normalized_text"]
                    fb.embedding = emb["embedding"]
                    fb.embedding_model = emb["embedding_model"]
                    fb.save(update_fields=["normalized_content", "embedding", "embedding_model", "updated_at"])

            # Store duplicate suggestions for human review (do NOT auto-confirm)
            enriched_candidates = []
            for pair in ai_result.get("duplicate_candidates", []):
                fa = fb_by_id.get(pair["feedback_a_id"])
                fb_item = fb_by_id.get(pair["feedback_b_id"])
                if fa and fb_item:
                    enriched_candidates.append(
                        {
                            "feedback_a_id": fa.id,
                            "feedback_a_code": fa.code,
                            "feedback_a_title": fa.title,
                            "feedback_b_id": fb_item.id,
                            "feedback_b_code": fb_item.code,
                            "feedback_b_title": fb_item.title,
                            "similarity_score": pair["similarity_score"],
                            "is_exact_normalized_match": pair.get("is_exact_normalized_match", False),
                        }
                    )
                    if not fb_item.duplicate_of_id and not fb_item.is_duplicate_confirmed:
                        fb_item.duplicate_of = fa
                        fb_item.similarity_score = pair["similarity_score"]
                        fb_item.save(update_fields=["duplicate_of", "similarity_score", "updated_at"])

            created_insight_ids = []
            for cluster in ai_result.get("clusters", []):
                members = cluster.get("members", [])
                if not members:
                    continue
                first_fb = fb_by_id.get(members[0]["feedback_id"])
                product = job.product or (first_fb.product if first_fb else None)
                if not product:
                    continue

                insight = InsightGroup.objects.create(
                    product=product,
                    title=cluster["title"][:255],
                    description=cluster["summary"],
                    possible_causes=cluster.get("possible_causes", []),
                    user_impact=cluster.get("user_impact", ""),
                    ai_recommendations=cluster.get("ai_recommendations", []),
                    draft_customer_reply=cluster.get("draft_customer_reply", ""),
                    analysis_mode=cluster.get("analysis_mode", "local_nlp"),
                    ai_confidence=float(cluster.get("ai_confidence", 0.75)),
                    volume_score=float(cluster["volume_score"]),
                    impact_score=float(cluster["impact_score"]),
                    severity_score=float(cluster["severity_score"]),
                    priority_score=float(cluster["priority_score"]),
                    priority_level=cluster["priority_level"],
                    priority_reasoning=cluster["priority_reasoning"],
                    status=InsightGroup.STATUS_NEW,
                    verification_status=InsightGroup.VERIFY_PENDING,
                    created_by=job.triggered_by,
                )

                for member in members:
                    fb = fb_by_id.get(member["feedback_id"])
                    if not fb:
                        continue
                    InsightFeedback.objects.get_or_create(
                        insight_group=insight,
                        feedback=fb,
                        defaults={
                            "similarity_to_centroid": member["similarity_to_centroid"],
                            "added_by_ai": True,
                            "added_by": job.triggered_by,
                        },
                    )
                    fb.priority_score = insight.priority_score
                    if fb.status == Feedback.STATUS_NEW:
                        fb.status = Feedback.STATUS_ANALYZING
                    fb.save(update_fields=["priority_score", "status", "updated_at"])

                insight.sync_counts()
                created_insight_ids.append(insight.id)

            job.status = AIAnalysisJob.STATUS_COMPLETED
            job.analysis_mode = ai_result.get("analysis_mode", "local_nlp")
            job.metrics = {
                **ai_result.get("stats", {}),
                "embedding_model": ai_result.get("embedding_model", ""),
                "created_insight_ids": created_insight_ids,
            }
            job.duplicate_candidates = enriched_candidates
            job.unassigned_feedback_ids = ai_result.get("unassigned_feedback_ids", [])
            job.completed_at = timezone.now()
            job.save()

            log_activity(
                job.triggered_by,
                ActivityLog.ENTITY_AI_JOB,
                job.id,
                "AI_PIPELINE_COMPLETED",
                (
                    f"AI Engine phân tích {job.metrics.get('processed_count', 0)} feedback: "
                    f"tạo {len(created_insight_ids)} nhóm insight, phát hiện "
                    f"{len(enriched_candidates)} cặp nghi trùng lặp."
                ),
                new_value=job.metrics,
            )

        return job

    except Exception as exc:
        logger.exception("AI pipeline execution failed for job=%s: %s", job_id, exc)
        job.status = AIAnalysisJob.STATUS_FAILED
        job.error_message = str(exc)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        return job


def rescore_and_summarize_insight(
    insight: InsightGroup,
    use_llm: bool = True,
    preserve_title: bool = True,
) -> InsightGroup:
    """Call AI Service /summarize to refresh summary/priority after manual merge/split/edit."""
    links = insight.insight_feedback_links.select_related("feedback__source").all()
    feedbacks = [link.feedback for link in links]
    if not feedbacks:
        insight.sync_counts()
        return insight

    total_inbox = Feedback.objects.filter(product=insight.product).count()
    payload = {
        "feedbacks": [serialize_feedback_for_ai(fb) for fb in feedbacks],
        "total_inbox_count": total_inbox,
        "use_llm": use_llm,
        "custom_title": insight.title if preserve_title else None,
    }

    try:
        with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
            resp = client.post(
                f"{settings.AI_SERVICE_URL}/summarize",
                json=payload,
                headers=_ai_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        insight.title = data["title"][:255]
        insight.description = data["summary"]
        insight.possible_causes = data.get("possible_causes", [])
        insight.user_impact = data.get("user_impact", "")
        insight.ai_recommendations = data.get("ai_recommendations", [])
        insight.draft_customer_reply = data.get("draft_customer_reply", "")
        insight.analysis_mode = data.get("analysis_mode", "local_nlp")
        insight.ai_confidence = float(data.get("ai_confidence", 0.75))
        insight.volume_score = float(data["volume_score"])
        insight.impact_score = float(data["impact_score"])
        insight.severity_score = float(data["severity_score"])
        if not insight.is_priority_overridden:
            insight.priority_score = float(data["priority_score"])
            insight.priority_level = data["priority_level"]
            insight.priority_reasoning = data["priority_reasoning"]
        insight.save()
    except Exception as exc:
        logger.warning("Failed to call AI summarize on insight=%s: %s", insight.id, exc)
    insight.sync_counts()
    return insight
