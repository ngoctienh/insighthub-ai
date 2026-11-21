from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role, User
from apps.feedbacks.models import Product
from apps.insights.models import InsightGroup
from apps.notifications.services import notify_roadmap_updated
from apps.roadmap.models import RoadmapItem
from apps.roadmap.serializers import RoadmapItemSerializer
from apps.web.decorators import render_forbidden, web_feature_required
from .helpers import format_serializer_error


def public_roadmap_view(request):
    qs = (
        RoadmapItem.objects.select_related("product")
        .prefetch_related("insight_groups")
        .filter(
            visibility=RoadmapItem.VISIBILITY_PUBLIC,
            status__in=[
                RoadmapItem.STATUS_PLANNED,
                RoadmapItem.STATUS_IN_PROGRESS,
                RoadmapItem.STATUS_COMPLETED,
            ],
        )
        .order_by("status", "-updated_at")
    )
    product_id = request.GET.get("product", "").strip()
    if product_id:
        qs = qs.filter(product_id=product_id)

    sanitized_items = []
    for item in qs:
        insights = list(item.insight_groups.all())
        sanitized_items.append(
            {
                "id": item.id,
                "code": item.code,
                "product_name": item.product.name,
                "title": item.title,
                "summary": item.public_description.strip() or item.description,
                "status": item.status,
                "quarter": item.quarter,
                "progress_percent": item.progress_percent,
                "total_linked_feedbacks": sum(ins.feedback_count for ins in insights),
            }
        )

    columns = [
        {
            "status": "PLANNED",
            "title": "Đã lên kế hoạch",
            "badge": "bg-amber-50 text-amber-800 border-amber-200",
            "items": [i for i in sanitized_items if i["status"] == "PLANNED"],
        },
        {
            "status": "IN_PROGRESS",
            "title": "Đang phát triển",
            "badge": "bg-blue-50 text-blue-800 border-blue-200",
            "items": [i for i in sanitized_items if i["status"] == "IN_PROGRESS"],
        },
        {
            "status": "COMPLETED",
            "title": "Đã ra mắt",
            "badge": "bg-emerald-50 text-emerald-800 border-emerald-200",
            "items": [i for i in sanitized_items if i["status"] == "COMPLETED"],
        },
    ]

    return render(
        request,
        "pages/public_roadmap.html",
        {
            "active_nav": "public_roadmap",
            "columns": columns,
            "products": Product.objects.filter(is_active=True),
            "selected_product": product_id,
        },
    )


@web_feature_required("roadmap")
def roadmap_view(request):
    can_edit = request.user.role_code in (Role.ADMIN, Role.PRODUCT_MANAGER)

    if request.method == "POST":
        if not can_edit:
            return render_forbidden(
                request,
                "Chỉ Product Manager hoặc Admin mới có quyền chỉnh sửa Roadmap.",
            )
        action = request.POST.get("action", "")
        if action in ("create", "edit"):
            insight_ids = [
                int(x) for x in request.POST.getlist("insight_group_ids") if str(x).isdigit()
            ]
            payload = {
                "product": request.POST.get("product"),
                "owner": request.POST.get("owner") or None,
                "title": request.POST.get("title", "").strip(),
                "description": request.POST.get("description", "").strip(),
                "public_description": request.POST.get("public_description", "").strip(),
                "status": request.POST.get("status", RoadmapItem.STATUS_PLANNED),
                "visibility": request.POST.get("visibility", RoadmapItem.VISIBILITY_PUBLIC),
                "quarter": request.POST.get("quarter", "Q1 2027").strip(),
                "progress_percent": int(request.POST.get("progress_percent", 0) or 0),
                "insight_group_ids": insight_ids,
            }
            if action == "edit":
                instance = get_object_or_404(RoadmapItem, pk=request.POST.get("item_id"))
                serializer = RoadmapItemSerializer(instance, data=payload, partial=True)
            else:
                serializer = RoadmapItemSerializer(data=payload)
            try:
                serializer.is_valid(raise_exception=True)
                saved = serializer.save()
                notify_roadmap_updated(saved, actor=request.user, created=(action == "create"))
                messages.success(
                    request,
                    f"Đã {'cập nhật' if action == 'edit' else 'tạo'} Roadmap item {saved.code}!",
                )
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
            return redirect("web-roadmap")

        if action == "delete":
            instance = get_object_or_404(RoadmapItem, pk=request.POST.get("item_id"))
            code = instance.code
            instance.delete()
            messages.info(request, f"Đã xóa {code}.")
            return redirect("web-roadmap")

    visibility_filter = request.GET.get("visibility", "").strip()
    search = request.GET.get("search", "").strip()
    qs = RoadmapItem.objects.select_related("product", "owner", "owner__role").prefetch_related(
        "insight_groups"
    )
    if visibility_filter in (RoadmapItem.VISIBILITY_PUBLIC, RoadmapItem.VISIBILITY_PRIVATE):
        qs = qs.filter(visibility=visibility_filter)
    if search:
        qs = qs.filter(
            Q(code__icontains=search) | Q(title__icontains=search) | Q(description__icontains=search)
        )

    items = list(qs)
    roadmap_payload = {
        str(item.id): {
            "id": item.id,
            "code": item.code,
            "product": item.product_id,
            "owner": item.owner_id or "",
            "title": item.title,
            "description": item.description,
            "public_description": item.public_description,
            "status": item.status,
            "visibility": item.visibility,
            "quarter": item.quarter,
            "progress_percent": item.progress_percent,
            "insight_ids": [ins.id for ins in item.insight_groups.all()],
        }
        for item in items
    }

    return render(
        request,
        "pages/roadmap.html",
        {
            "active_nav": "roadmap",
            "items": items,
            "visibility_filter": visibility_filter,
            "search": search,
            "can_edit": can_edit,
            "products": Product.objects.filter(is_active=True),
            "insights": InsightGroup.objects.exclude(
                verification_status=InsightGroup.VERIFY_REJECTED
            )[:100],
            "staff": User.objects.select_related("role")
            .filter(is_active=True)
            .exclude(role__code=Role.CUSTOMER),
            "roadmap_payload": roadmap_payload,
        },
    )
