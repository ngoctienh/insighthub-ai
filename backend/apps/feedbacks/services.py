import logging
from datetime import timedelta
from typing import Any, Optional

import httpx
from django.conf import settings
from django.db.models import Count, Q, QuerySet
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.models import Role, User
from apps.insights.models import InsightGroup
from .models import Feedback

logger = logging.getLogger(__name__)


def get_scoped_feedbacks(user: User) -> QuerySet[Feedback]:
    """Return feedbacks visible to the given user according to row-level RBAC."""
    role = user.role_code
    qs = (
        Feedback.objects.select_related(
            "product",
            "source",
            "assigned_to",
            "assigned_to__role",
            "author",
            "duplicate_of",
        )
        .prefetch_related("tags", "insight_groups")
        .annotate(annotated_votes_count=Count("votes", distinct=True))
    )
    if role == Role.CUSTOMER:
        qs = qs.filter(Q(author=user) | Q(sender_email__iexact=user.email))
    elif role == Role.DEVELOPER:
        qs = qs.filter(Q(assigned_to=user) | Q(insight_groups__assigned_to=user)).distinct()
    return qs


def apply_feedback_filters(
    qs: QuerySet[Feedback],
    params: dict[str, Any],
    user: Optional[User] = None,
) -> QuerySet[Feedback]:
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(title__icontains=search)
            | Q(content__icontains=search)
            | Q(sender_name__icontains=search)
            | Q(sender_email__icontains=search)
        )

    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("source"):
        qs = qs.filter(source__code=params["source"])
    if params.get("impact_level"):
        qs = qs.filter(impact_level=params["impact_level"])
    if params.get("product"):
        qs = qs.filter(product_id=params["product"])
    if params.get("assigned_to"):
        if params["assigned_to"] == "unassigned":
            qs = qs.filter(assigned_to__isnull=True)
        else:
            qs = qs.filter(assigned_to_id=params["assigned_to"])
    if params.get("tag"):
        tag_param = params["tag"]
        if str(tag_param).isdigit():
            qs = qs.filter(tags__id=int(tag_param))
        else:
            qs = qs.filter(tags__slug=tag_param)

    priority_level = params.get("priority_level")
    if priority_level == "CRITICAL":
        qs = qs.filter(Q(priority_score__gte=80) | Q(impact_level="CRITICAL"))
    elif priority_level == "HIGH":
        qs = qs.filter(Q(priority_score__gte=60, priority_score__lt=80) | Q(impact_level="HIGH"))
    elif priority_level == "MEDIUM":
        qs = qs.filter(Q(priority_score__gte=40, priority_score__lt=60) | Q(impact_level="MEDIUM"))
    elif priority_level == "LOW":
        qs = qs.filter(Q(priority_score__lt=40) | Q(impact_level="LOW"))

    if params.get("date_from"):
        d = parse_date(str(params["date_from"]))
        if d:
            qs = qs.filter(created_at__date__gte=d)
    if params.get("date_to"):
        d = parse_date(str(params["date_to"]))
        if d:
            qs = qs.filter(created_at__date__lte=d)

    if str(params.get("unclustered_only", "")).lower() in ("1", "true", "on"):
        qs = qs.filter(insight_links__isnull=True)
    if str(params.get("duplicate_only", "")).lower() in ("1", "true", "on"):
        qs = qs.filter(Q(status=Feedback.STATUS_DUPLICATE) | Q(duplicate_of__isnull=False))
    if user and str(params.get("mine_only", "")).lower() in ("1", "true", "on"):
        qs = qs.filter(Q(author=user) | Q(assigned_to=user))

    ordering = params.get("ordering") or "-created_at"
    allowed_orderings = {
        "-created_at",
        "created_at",
        "-priority_score",
        "priority_score",
        "-id",
        "id",
    }
    if ordering in allowed_orderings:
        qs = qs.order_by(ordering, "-id")
    return qs


def find_similar_feedbacks(
    feedback: Feedback,
    top_k: int = 6,
    min_similarity: float = 0.35,
) -> dict[str, Any]:
    candidates = list(
        Feedback.objects.select_related("source")
        .filter(product=feedback.product)
        .exclude(id=feedback.id)
        .order_by("-created_at")[:120]
    )
    if not candidates:
        return {"embedding_model": "none", "matches": []}

    payload = {
        "target": {
            "id": feedback.id,
            "code": feedback.code,
            "title": feedback.title,
            "content": feedback.content,
            "impact_level": feedback.impact_level,
            "votes_count": feedback.votes.count(),
            "sender_email": feedback.sender_email,
            "sender_name": feedback.sender_name,
            "source_code": feedback.source.code,
        },
        "candidates": [
            {
                "id": item.id,
                "code": item.code,
                "title": item.title,
                "content": item.content,
                "impact_level": item.impact_level,
                "votes_count": 0,
                "sender_email": item.sender_email,
                "sender_name": item.sender_name,
                "source_code": item.source.code,
            }
            for item in candidates
        ],
        "top_k": top_k,
        "min_similarity": min_similarity,
        "use_llm": True,
    }

    headers = {}
    if settings.AI_SERVICE_API_KEY:
        headers["X-API-Key"] = settings.AI_SERVICE_API_KEY

    with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
        resp = client.post(
            f"{settings.AI_SERVICE_URL}/similarity/search",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


def build_dashboard_data(
    user: User,
    product_id: Optional[str | int] = None,
    days: int = 30,
) -> dict[str, Any]:
    days = min(90, max(7, int(days)))
    role = user.role_code

    fb_qs = Feedback.objects.all()
    insight_qs = InsightGroup.objects.exclude(verification_status=InsightGroup.VERIFY_REJECTED)

    if product_id:
        fb_qs = fb_qs.filter(product_id=product_id)
        insight_qs = insight_qs.filter(product_id=product_id)

    if role == Role.CUSTOMER:
        fb_qs = fb_qs.filter(Q(author=user) | Q(sender_email__iexact=user.email))
    elif role == Role.DEVELOPER:
        fb_qs = fb_qs.filter(Q(assigned_to=user) | Q(insight_groups__assigned_to=user)).distinct()
        insight_qs = insight_qs.filter(assigned_to=user)

    total_feedbacks = fb_qs.count()
    new_feedbacks = fb_qs.filter(status=Feedback.STATUS_NEW).count()
    in_progress_feedbacks = fb_qs.filter(
        status__in=[Feedback.STATUS_REVIEWING, Feedback.STATUS_PLANNED]
    ).count()
    done_feedbacks = fb_qs.filter(status=Feedback.STATUS_DONE).count()
    duplicate_feedbacks = fb_qs.filter(
        Q(status=Feedback.STATUS_DUPLICATE) | Q(is_duplicate_confirmed=True)
    ).count()

    insights_detected = 0 if role == Role.CUSTOMER else insight_qs.count()

    start_date = timezone.now() - timedelta(days=days - 1)
    by_date_rows = (
        fb_qs.filter(created_at__gte=start_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    day_map = {row["day"].isoformat(): row["count"] for row in by_date_rows if row["day"]}
    feedbacks_by_date = []
    for offset in range(days):
        d = (start_date + timedelta(days=offset)).date().isoformat()
        feedbacks_by_date.append({"date": d, "count": day_map.get(d, 0)})

    source_rows = (
        fb_qs.values("source__code", "source__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    feedbacks_by_source = [
        {"source_code": r["source__code"], "name": r["source__name"], "count": r["count"]}
        for r in source_rows
    ]

    status_rows = fb_qs.values("status").annotate(count=Count("id"))
    status_map = {r["status"]: r["count"] for r in status_rows}
    feedbacks_by_status = [
        {"status": st, "count": status_map.get(st, 0)}
        for st in ["NEW", "REVIEWING", "PLANNED", "DONE", "DUPLICATE"]
    ]

    tag_rows = (
        fb_qs.filter(tags__isnull=False)
        .values("tags__name", "tags__color")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    feedbacks_by_tag = [
        {"name": r["tags__name"], "color": r["tags__color"], "count": r["count"]}
        for r in tag_rows
    ]

    if role == Role.CUSTOMER:
        priority_rows = fb_qs.values("impact_level").annotate(count=Count("id"))
        priority_map = {r["impact_level"]: r["count"] for r in priority_rows}
    else:
        priority_rows = insight_qs.values("priority_level").annotate(count=Count("id"))
        priority_map = {r["priority_level"]: r["count"] for r in priority_rows}

    by_priority = [
        {"level": lvl, "count": priority_map.get(lvl, 0)}
        for lvl in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    ]

    top_5_issues = []
    urgent_insights = []
    if role != Role.CUSTOMER:
        top_5_qs = insight_qs.prefetch_related("insight_feedback_links__feedback").order_by(
            "-feedback_count", "-priority_score"
        )[:5]
        top_5_issues = [
            {
                "id": ins.id,
                "code": ins.code,
                "title": ins.title,
                "feedback_count": ins.feedback_count,
                "affected_customers_count": ins.affected_customers_count,
                "priority_score": ins.priority_score,
                "priority_level": ins.priority_level,
                "status": ins.status,
            }
            for ins in top_5_qs
        ]

        urgent_qs = (
            insight_qs.prefetch_related("insight_feedback_links__feedback")
            .filter(priority_level__in=["CRITICAL", "HIGH"])
            .exclude(status=InsightGroup.STATUS_DONE)
            .order_by("-priority_score")[:6]
        )
        urgent_insights = [
            {
                "id": ins.id,
                "code": ins.code,
                "title": ins.title,
                "priority_score": ins.priority_score,
                "priority_level": ins.priority_level,
                "feedback_count": ins.feedback_count,
                "affected_customers_count": ins.affected_customers_count,
                "status": ins.status,
                "verification_status": ins.verification_status,
            }
            for ins in urgent_qs
        ]

    return {
        "kpis": {
            "total_feedbacks": total_feedbacks,
            "new_feedbacks": new_feedbacks,
            "insights_detected": insights_detected,
            "in_progress_issues": in_progress_feedbacks,
            "completed_issues": done_feedbacks,
            "duplicate_feedbacks": duplicate_feedbacks,
        },
        "feedbacks_by_date": feedbacks_by_date,
        "feedbacks_by_source": feedbacks_by_source,
        "feedbacks_by_status": feedbacks_by_status,
        "feedbacks_by_tag": feedbacks_by_tag,
        "by_priority": by_priority,
        "top_5_issues": top_5_issues,
        "urgent_insights": urgent_insights,
    }
