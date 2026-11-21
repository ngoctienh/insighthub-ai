import math
import re
from typing import Tuple

from .schemas import FeedbackInput, PriorityLevel


_IMPACT_WEIGHTS = {
    "CRITICAL": 95.0,
    "HIGH": 75.0,
    "MEDIUM": 48.0,
    "LOW": 22.0,
}

_CORE_IMPACT_PATTERN = re.compile(
    r"\b(thanh toán|giao dịch|đặt hàng|đặt món|đăng nhập|giỏ hàng|giao hàng|tài xế|shipper|otp|ví|thẻ)\b",
    re.IGNORECASE,
)

_SEVERE_FAILURE_PATTERN = re.compile(
    r"\b(không thể|thất bại|lỗi|treo|crash|văng|trừ tiền|mất tiền|sập|đứng máy|sai địa chỉ|không nhận được|hỏng|nghiêm trọng|bảo mật|rò rỉ)\b",
    re.IGNORECASE,
)


_PRIORITY_LABELS = {
    "CRITICAL": "Nghiêm trọng",
    "HIGH": "Cao",
    "MEDIUM": "Trung bình",
    "LOW": "Thấp",
}


def classify_priority(score: float) -> PriorityLevel:
    if score >= 80.0:
        return "CRITICAL"
    if score >= 60.0:
        return "HIGH"
    if score >= 40.0:
        return "MEDIUM"
    return "LOW"


def calculate_priority_score(
    feedbacks: list[FeedbackInput],
    total_inbox_count: int | None = None,
) -> dict:
    """
    Compute Priority = 0.40 * V + 0.35 * I + 0.25 * S on normalized [0..100] scale.
    Returns scores, level, affected_customers_count, and human-readable reasoning.
    """
    if not feedbacks:
        return {
            "volume_score": 0.0,
            "impact_score": 0.0,
            "severity_score": 0.0,
            "priority_score": 0.0,
            "priority_level": "LOW",
            "affected_customers_count": 0,
            "priority_reasoning": "Không có feedback nào trong nhóm để tính điểm ưu tiên.",
        }

    cluster_size = len(feedbacks)
    unique_senders = {
        (fb.sender_email or fb.sender_name or f"id:{fb.id}").strip().lower()
        for fb in feedbacks
    }
    affected_customers_count = len(unique_senders)
    total_votes = sum(max(0, fb.votes_count) for fb in feedbacks)

    baseline_total = max(total_inbox_count or cluster_size, cluster_size, 10)
    reference_cluster_target = max(6.0, baseline_total * 0.22)
    volume_ratio = math.log1p(cluster_size) / math.log1p(reference_cluster_target)
    volume_base = min(82.0, volume_ratio * 82.0)
    customer_reach_bonus = min(12.0, affected_customers_count * 1.8)
    vote_bonus = min(6.0, total_votes * 0.45)
    volume_score = round(min(100.0, volume_base + customer_reach_bonus + vote_bonus), 1)

    impact_values = [_IMPACT_WEIGHTS.get(fb.impact_level, 48.0) for fb in feedbacks]
    avg_impact = sum(impact_values) / cluster_size
    core_hits = sum(
        1
        for fb in feedbacks
        if _CORE_IMPACT_PATTERN.search(f"{fb.title} {fb.content}")
    )
    core_ratio = core_hits / cluster_size
    impact_score = round(min(100.0, avg_impact * 0.85 + core_ratio * 18.0), 1)

    high_or_critical = sum(
        1 for fb in feedbacks if fb.impact_level in ("CRITICAL", "HIGH")
    )
    severe_hits = sum(
        1
        for fb in feedbacks
        if _SEVERE_FAILURE_PATTERN.search(f"{fb.title} {fb.content}")
    )
    critical_count = sum(1 for fb in feedbacks if fb.impact_level == "CRITICAL")

    severity_raw = (
        (high_or_critical / cluster_size) * 52.0
        + (severe_hits / cluster_size) * 33.0
        + (critical_count / cluster_size) * 15.0
    )
    severity_score = round(min(100.0, max(15.0, severity_raw)), 1)

    priority_score = round(
        0.40 * volume_score + 0.35 * impact_score + 0.25 * severity_score,
        1,
    )
    priority_level = classify_priority(priority_score)
    priority_label = _PRIORITY_LABELS.get(priority_level, priority_level)

    reasoning = (
        f"Điểm tổng hợp {priority_score}/100 ({priority_label}) = "
        f"0.40×Số lượng({volume_score}) + 0.35×Tác động({impact_score}) + 0.25×Nghiêm trọng({severity_score}). "
        f"Nhóm gồm {cluster_size} feedback từ {affected_customers_count} khách hàng "
        f"(tổng {total_votes} lượt bình chọn); có {critical_count} báo cáo mức Nghiêm trọng, "
        f"{high_or_critical}/{cluster_size} báo cáo mức Cao/Nghiêm trọng và "
        f"{severe_hits}/{cluster_size} phản hồi chứa dấu hiệu lỗi hoặc chặn luồng nghiêm trọng."
    )

    return {
        "volume_score": volume_score,
        "impact_score": impact_score,
        "severity_score": severity_score,
        "priority_score": priority_score,
        "priority_level": priority_level,
        "affected_customers_count": affected_customers_count,
        "priority_reasoning": reasoning,
    }
