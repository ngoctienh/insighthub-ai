import logging
from typing import Any, Optional

import httpx
from celery.result import AsyncResult
from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet

from apps.accounts.models import Role, User
from apps.feedbacks.models import Feedback
from apps.notifications.services import notify_insight_status_changed
from insighthub.celery import app as celery_app
from .models import InsightFeedback, InsightGroup

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
        "submitted_at": feedback.created_at.isoformat() if feedback.created_at else None,
    }


def classify_priority_level(score: float) -> str:
    if score >= 80:
        return InsightGroup.PRIORITY_CRITICAL
    if score >= 60:
        return InsightGroup.PRIORITY_HIGH
    if score >= 40:
        return InsightGroup.PRIORITY_MEDIUM
    return InsightGroup.PRIORITY_LOW


def get_scoped_insights(user: User) -> QuerySet[InsightGroup]:
    qs = (
        InsightGroup.objects.select_related("product", "assigned_to", "assigned_to__role")
        .prefetch_related("insight_feedback_links__feedback__source", "roadmap_items")
    )
    if user.role_code in (Role.DEVELOPER, Role.CUSTOMER_SUPPORT):
        qs = qs.filter(
            Q(assigned_to=user) | Q(verification_status=InsightGroup.VERIFY_CONFIRMED)
        ).distinct()
    return qs


def get_duplicate_candidates_list(product_id: Optional[str | int] = None) -> list[dict[str, Any]]:
    qs = (
        Feedback.objects.select_related("duplicate_of")
        .filter(duplicate_of__isnull=False, is_duplicate_confirmed=False)
        .order_by("-similarity_score", "-id")
    )
    if product_id:
        qs = qs.filter(product_id=product_id)
    return [
        {
            "feedback_a_id": fb.duplicate_of_id,
            "feedback_a_code": fb.duplicate_of.code,
            "feedback_a_title": fb.duplicate_of.title,
            "feedback_b_id": fb.id,
            "feedback_b_code": fb.code,
            "feedback_b_title": fb.title,
            "similarity_score": fb.similarity_score or 0.0,
            "is_exact_normalized_match": (fb.similarity_score or 0.0) >= 0.99,
        }
        for fb in qs[:50]
    ]


def get_unassigned_feedbacks_queryset(product_id: Optional[str | int] = None) -> QuerySet[Feedback]:
    grouped_ids = InsightFeedback.objects.exclude(
        insight_group__verification_status=InsightGroup.VERIFY_REJECTED
    ).values_list("feedback_id", flat=True)
    qs = (
        Feedback.objects.select_related("product", "source", "assigned_to")
        .prefetch_related("tags", "insight_groups")
        .filter(is_duplicate_confirmed=False)
        .exclude(id__in=grouped_ids)
    )
    if product_id:
        qs = qs.filter(product_id=product_id)
    return qs


def execute_ai_pipeline(
    config: Optional[dict[str, Any]] = None,
    product_id: Optional[int] = None,
) -> dict[str, Any]:
    cfg = config or {}
    similarity_threshold = float(cfg.get("similarity_threshold", 0.72))
    eps = float(cfg.get("eps", 0.48))
    min_samples = int(cfg.get("min_samples", 2))
    use_llm = bool(cfg.get("use_llm", True))
    include_clustered = bool(cfg.get("include_clustered", False))

    fb_qs = Feedback.objects.select_related("source", "product").filter(
        is_duplicate_confirmed=False
    )
    if product_id:
        fb_qs = fb_qs.filter(product_id=product_id)

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
        return {
            "status": "COMPLETED",
            "analysis_mode": "local_nlp",
            "metrics": {
                "input_count": 0,
                "processed_count": 0,
                "clusters_count": 0,
                "duplicate_candidates_count": 0,
                "unassigned_count": 0,
                "created_insight_ids": [],
                "message": "Không có feedback mới chưa phân nhóm để phân tích.",
            },
            "duplicate_candidates": [],
            "unassigned_feedback_ids": [],
        }

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
            if product_id:
                pending_qs = pending_qs.filter(product_id=product_id)
            pending_qs.delete()

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
            product = first_fb.product if first_fb else None
            if not product:
                continue

            insight = InsightGroup.objects.create(
                product=product,
                title=cluster["title"][:255],
                description=cluster["summary"],
                possible_causes=cluster.get("possible_causes", []),
                ai_recommendations=cluster.get("ai_recommendations", []),
                draft_customer_reply=cluster.get("draft_customer_reply", ""),
                volume_score=float(cluster["volume_score"]),
                impact_score=float(cluster["impact_score"]),
                severity_score=float(cluster["severity_score"]),
                priority_score=float(cluster["priority_score"]),
                priority_level=cluster["priority_level"],
                status=InsightGroup.STATUS_NEW,
                verification_status=InsightGroup.VERIFY_PENDING,
            )

            for member in members:
                fb = fb_by_id.get(member["feedback_id"])
                if not fb:
                    continue
                InsightFeedback.objects.get_or_create(
                    insight_group=insight,
                    feedback=fb,
                    defaults={"similarity_to_centroid": member["similarity_to_centroid"]},
                )
                fb.priority_score = insight.priority_score
                if fb.status == Feedback.STATUS_NEW:
                    fb.status = Feedback.STATUS_REVIEWING
                fb.save(update_fields=["priority_score", "status", "updated_at"])

            insight.sync_counts()
            created_insight_ids.append(insight.id)

    return {
        "status": "COMPLETED",
        "analysis_mode": ai_result.get("analysis_mode", "local_nlp"),
        "metrics": {
            **ai_result.get("stats", {}),
            "embedding_model": ai_result.get("embedding_model", ""),
            "created_insight_ids": created_insight_ids,
        },
        "duplicate_candidates": enriched_candidates,
        "unassigned_feedback_ids": ai_result.get("unassigned_feedback_ids", []),
    }


def get_ai_task_status(task_id: str) -> dict[str, Any]:
    """Query Celery AsyncResult state in a normalized format for API and Web polling."""
    res = AsyncResult(task_id, app=celery_app)
    state = res.state
    if state == "SUCCESS":
        return {
            "task_id": task_id,
            "state": "SUCCESS",
            "ready": True,
            "result": res.result if isinstance(res.result, dict) else {},
        }
    if state in ("FAILURE", "REVOKED"):
        return {
            "task_id": task_id,
            "state": "FAILURE",
            "ready": True,
            "detail": str(res.info or "Tác vụ AI gặp lỗi khi xử lý."),
        }
    return {
        "task_id": task_id,
        "state": state,
        "ready": False,
    }


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
        insight.ai_recommendations = data.get("ai_recommendations", [])
        insight.draft_customer_reply = data.get("draft_customer_reply", "")
        insight.volume_score = float(data["volume_score"])
        insight.impact_score = float(data["impact_score"])
        insight.severity_score = float(data["severity_score"])
        insight.priority_score = float(data["priority_score"])
        insight.priority_level = data["priority_level"]
        insight.save()
    except Exception as exc:
        logger.warning("Failed to call AI summarize on insight=%s: %s", insight.id, exc)
    insight.sync_counts()
    return insight


def summarize_single_feedback(feedback: Feedback, use_llm: bool = True) -> dict[str, Any]:
    """Generate and persist a concise AI summary directly onto feedback.ai_summary."""
    payload = {
        "feedbacks": [serialize_feedback_for_ai(feedback)],
        "total_inbox_count": Feedback.objects.filter(product=feedback.product).count(),
        "use_llm": use_llm,
    }
    with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
        resp = client.post(
            f"{settings.AI_SERVICE_URL}/summarize",
            json=payload,
            headers=_ai_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    summary_text = (data.get("summary") or "").strip()
    feedback.ai_summary = summary_text
    if feedback.priority_score is None and data.get("priority_score") is not None:
        feedback.priority_score = float(data["priority_score"])
        feedback.save(update_fields=["ai_summary", "priority_score", "updated_at"])
    else:
        feedback.save(update_fields=["ai_summary", "updated_at"])

    return {
        "ai_summary": feedback.ai_summary,
        "priority_score": feedback.priority_score,
        "recommendations": data.get("ai_recommendations", []),
        "analysis_mode": data.get("analysis_mode", "local_nlp"),
    }


def regenerate_insight_reply(
    insight: InsightGroup,
    tone: str = "empathetic",
    use_llm: bool = True,
) -> dict[str, Any]:
    samples = [
        f"{link.feedback.title}: {link.feedback.content}"
        for link in insight.insight_feedback_links.select_related("feedback").all()[:5]
    ]
    with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
        resp = client.post(
            f"{settings.AI_SERVICE_URL}/draft-reply",
            json={
                "insight_title": insight.title,
                "insight_summary": insight.description,
                "sample_feedbacks": samples,
                "tone": tone,
                "use_llm": use_llm,
            },
            headers=_ai_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
    insight.draft_customer_reply = data["draft_reply"]
    insight.save(update_fields=["draft_customer_reply"])
    return {
        "draft_customer_reply": insight.draft_customer_reply,
        "analysis_mode": data["analysis_mode"],
        "tone": data["tone"],
    }


def broadcast_insight_reply(
    insight: InsightGroup,
    user: User,
    message: str,
    save_draft: bool = True,
) -> dict[str, int]:
    """Save optional draft edit and send a manual reply to every feedback in this Insight."""
    from apps.feedbacks.services import send_feedback_reply

    cleaned = (message or "").strip()
    if not cleaned:
        raise ValueError("Nội dung phản hồi không được để trống.")

    with transaction.atomic():
        if save_draft:
            insight.draft_customer_reply = cleaned
            insight.save(update_fields=["draft_customer_reply"])

        links = insight.insight_feedback_links.select_related("feedback__author").all()
        sent_fb_ids: set[int] = set()
        notified_users: set[int] = set()
        for link in links:
            fb = link.feedback
            if fb.id in sent_fb_ids:
                continue
            sent_fb_ids.add(fb.id)
            send_feedback_reply(fb, user, cleaned)
            if fb.author_id and fb.author_id != user.id:
                notified_users.add(fb.author_id)

    return {
        "sent_feedback_count": len(sent_fb_ids),
        "notified_users_count": len(notified_users),
    }


def merge_insights(target: InsightGroup, source: InsightGroup) -> InsightGroup:
    with transaction.atomic():
        for link in source.insight_feedback_links.all():
            InsightFeedback.objects.get_or_create(
                insight_group=target,
                feedback=link.feedback,
                defaults={"similarity_to_centroid": link.similarity_to_centroid},
            )
        source.delete()
        rescore_and_summarize_insight(target, use_llm=False, preserve_title=True)
    return target


def split_insight(
    source: InsightGroup,
    links: list[InsightFeedback],
    new_title: str,
) -> InsightGroup:
    with transaction.atomic():
        new_group = InsightGroup.objects.create(
            product=source.product,
            title=new_title[:255],
            status=InsightGroup.STATUS_NEW,
            verification_status=InsightGroup.VERIFY_CONFIRMED,
        )
        for link in links:
            InsightFeedback.objects.create(
                insight_group=new_group,
                feedback=link.feedback,
            )
            link.delete()

        rescore_and_summarize_insight(source, use_llm=False, preserve_title=True)
        rescore_and_summarize_insight(new_group, use_llm=False, preserve_title=True)
    return new_group


def move_insight_kanban(
    insight: InsightGroup,
    actor: User,
    new_status: Optional[str] = None,
    assignee: Optional[User] = None,
    update_assignee: bool = False,
) -> InsightGroup:
    old_status = insight.status
    if new_status and new_status != old_status:
        insight.status = new_status
    if update_assignee:
        insight.assigned_to = assignee
    insight.save()

    if new_status in (
        InsightGroup.STATUS_REVIEWING,
        InsightGroup.STATUS_PLANNED,
        InsightGroup.STATUS_DONE,
    ):
        Feedback.objects.filter(
            insight_links__insight_group=insight,
            is_duplicate_confirmed=False,
        ).update(status=new_status)

    if new_status and new_status != old_status:
        notify_insight_status_changed(insight, old_status, new_status, actor=actor)
    return insight
