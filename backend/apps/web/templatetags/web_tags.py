from django import template
from django.utils.html import format_html

register = template.Library()

PRIORITY_STYLES = {
    "CRITICAL": "bg-rose-50 text-rose-700 border-rose-200",
    "HIGH": "bg-orange-50 text-orange-700 border-orange-200",
    "MEDIUM": "bg-amber-50 text-amber-700 border-amber-200",
    "LOW": "bg-slate-100 text-slate-700 border-slate-200",
}

STATUS_STYLES = {
    "NEW": "bg-sky-50 text-sky-700 border-sky-200",
    "REVIEWING": "bg-violet-50 text-violet-700 border-violet-200",
    "PLANNED": "bg-amber-50 text-amber-700 border-amber-200",
    "DONE": "bg-emerald-50 text-emerald-700 border-emerald-200",
    "IN_PROGRESS": "bg-blue-50 text-blue-700 border-blue-200",
    "COMPLETED": "bg-emerald-50 text-emerald-700 border-emerald-200",
    "DUPLICATE": "bg-zinc-100 text-zinc-600 border-zinc-300",
    "PENDING_REVIEW": "bg-amber-50 text-amber-700 border-amber-200",
    "CONFIRMED": "bg-emerald-50 text-emerald-700 border-emerald-200",
    "REJECTED": "bg-rose-50 text-rose-700 border-rose-200",
}

STATUS_LABELS = {
    "NEW": "New",
    "REVIEWING": "Reviewing",
    "PLANNED": "Planned",
    "DONE": "Done",
    "IN_PROGRESS": "In Progress",
    "COMPLETED": "Completed",
    "DUPLICATE": "Duplicate",
    "PENDING_REVIEW": "Chờ xác nhận",
    "CONFIRMED": "Đã xác nhận",
    "REJECTED": "Đã từ chối",
}

SOURCE_CONFIG = {
    "WEB_FORM": ("Website Form", "bg-indigo-50 text-indigo-700 border-indigo-200"),
    "EMAIL": ("Email", "bg-cyan-50 text-cyan-700 border-cyan-200"),
    "LIVE_CHAT": ("Live Chat", "bg-emerald-50 text-emerald-700 border-emerald-200"),
    "COMMUNITY": ("Cộng đồng", "bg-purple-50 text-purple-700 border-purple-200"),
}


@register.simple_tag
def priority_badge(level: str, score=None):
    cls = PRIORITY_STYLES.get(level or "LOW", PRIORITY_STYLES["LOW"])
    if score is not None and score != "":
        return format_html(
            '<span class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold {}">{} <span class="opacity-80">· {}</span></span>',
            cls,
            level,
            score,
        )
    return format_html(
        '<span class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold {}">{}</span>',
        cls,
        level,
    )


@register.simple_tag
def status_badge(status_val: str):
    cls = STATUS_STYLES.get(status_val or "NEW", STATUS_STYLES["NEW"])
    label = STATUS_LABELS.get(status_val, status_val)
    return format_html(
        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium {}">{}</span>',
        cls,
        label,
    )


@register.simple_tag
def source_badge(code: str):
    label, cls = SOURCE_CONFIG.get(code or "WEB_FORM", SOURCE_CONFIG["WEB_FORM"])
    return format_html(
        '<span class="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium {}">{}</span>',
        cls,
        label,
    )


@register.filter
def has_perm(user, feature_key: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.has_feature_permission(feature_key)


@register.filter
def has_role(user, roles_csv: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    allowed = {r.strip() for r in roles_csv.split(",") if r.strip()}
    return user.role_code in allowed


@register.filter
def mul100(value) -> str:
    try:
        return f"{float(value) * 100:.1f}"
    except (TypeError, ValueError):
        return "0.0"


@register.filter
def clamp100(value) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0
