import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role, User
from apps.feedbacks.models import Feedback, FeedbackSource, FeedbackTag, Product, Tag
from apps.feedbacks.serializers import FeedbackWriteSerializer, MultiSourceIngestSerializer
from apps.feedbacks.services import (
    apply_feedback_filters,
    build_dashboard_data,
    find_similar_feedbacks,
    get_scoped_feedbacks,
)
from apps.insights.services import summarize_single_feedback
from apps.notifications.models import Notification, Vote
from apps.notifications.services import (
    notify_feedback_assigned,
    notify_feedback_received,
    notify_feedback_status_changed,
)
from apps.web.decorators import is_json_request, render_forbidden, web_feature_required
from .helpers import format_serializer_error

logger = logging.getLogger(__name__)


def _mark_voted_flags(feedbacks, user):
    fb_list = list(feedbacks)
    fb_ids = [fb.id for fb in fb_list]
    voted_ids = set(
        Vote.objects.filter(user=user, feedback_id__in=fb_ids).values_list("feedback_id", flat=True)
    )
    for fb in fb_list:
        fb.user_has_voted = fb.id in voted_ids
        if not hasattr(fb, "annotated_votes_count"):
            fb.annotated_votes_count = fb.votes.count()
    return fb_list


@login_required
def portal_view(request):
    products = list(Product.objects.filter(is_active=True))
    tags = list(Tag.objects.all())

    if request.method == "POST":
        product_id = request.POST.get("product") or (products[0].id if products else None)
        tag_ids = [int(x) for x in request.POST.getlist("tag_ids") if str(x).isdigit()]
        serializer = FeedbackWriteSerializer(
            data={
                "product": product_id,
                "source_code": FeedbackSource.WEB_FORM,
                "title": request.POST.get("title", "").strip(),
                "content": request.POST.get("content", "").strip(),
                "impact_level": request.POST.get("impact_level", Feedback.IMPACT_MEDIUM),
                "tag_ids": tag_ids,
            },
            context={"request": request},
        )
        try:
            serializer.is_valid(raise_exception=True)
            fb = serializer.save()
            notify_feedback_received(fb, actor=request.user)
            messages.success(
                request,
                "Đã gửi phản hồi thành công! Đội ngũ sản phẩm sẽ sớm xem xét.",
            )
            return redirect("web-portal")
        except ValidationError as exc:
            messages.error(request, format_serializer_error(exc))

    my_feedbacks = list(get_scoped_feedbacks(request.user).order_by("-created_at")[:20])
    step_order = ["NEW", "REVIEWING", "PLANNED", "DONE"]
    for fb in my_feedbacks:
        idx = step_order.index(fb.status) if fb.status in step_order else 0
        fb.step_index = idx

    notifications = list(Notification.objects.filter(recipient=request.user)[:5])

    return render(
        request,
        "pages/portal.html",
        {
            "active_nav": "portal",
            "products": products,
            "tags": tags,
            "my_feedbacks": my_feedbacks,
            "notifications": notifications,
            "step_order": step_order,
        },
    )


@web_feature_required("dashboard")
def dashboard_view(request):
    product_id = request.GET.get("product", "").strip()
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    days = min(90, max(7, days))

    data = build_dashboard_data(
        request.user,
        product_id=product_id or None,
        days=days,
    )
    products = list(Product.objects.filter(is_active=True))

    return render(
        request,
        "pages/dashboard.html",
        {
            "active_nav": "dashboard",
            "data": data,
            "dashboard_json": data,
            "products": products,
            "selected_product": product_id,
            "selected_days": days,
        },
    )


@web_feature_required("inbox")
def inbox_view(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create_feedback":
            tag_ids = [int(x) for x in request.POST.getlist("tag_ids") if str(x).isdigit()]
            payload = {
                "product": request.POST.get("product"),
                "source_code": request.POST.get("source_code", FeedbackSource.WEB_FORM),
                "title": request.POST.get("title", "").strip(),
                "content": request.POST.get("content", "").strip(),
                "impact_level": request.POST.get("impact_level", Feedback.IMPACT_MEDIUM),
                "sender_name": request.POST.get("sender_name", "").strip(),
                "sender_email": request.POST.get("sender_email", "").strip(),
                "tag_ids": tag_ids,
            }
            serializer = FeedbackWriteSerializer(data=payload, context={"request": request})
            try:
                serializer.is_valid(raise_exception=True)
                fb = serializer.save()
                notify_feedback_received(fb, actor=request.user)
                messages.success(request, f"Đã tạo feedback {fb.code} thành công!")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
            return redirect("web-inbox")

        if action == "vote":
            fb = get_object_or_404(get_scoped_feedbacks(request.user), pk=request.POST.get("feedback_id"))
            existing = Vote.objects.filter(user=request.user, feedback=fb).first()
            if existing:
                existing.delete()
                voted = False
            else:
                Vote.objects.create(user=request.user, feedback=fb)
                voted = True
            if is_json_request(request):
                return JsonResponse({"voted": voted, "votes_count": fb.votes.count()})
            return redirect(request.META.get("HTTP_REFERER") or "web-inbox")

        if action == "delete":
            fb = get_object_or_404(get_scoped_feedbacks(request.user), pk=request.POST.get("feedback_id"))
            role = request.user.role_code
            allowed = role in (Role.ADMIN, Role.PRODUCT_MANAGER) or (
                role == Role.CUSTOMER and fb.author_id == request.user.id and fb.status == Feedback.STATUS_NEW
            )
            if not allowed:
                return render_forbidden(request, "Bạn không có quyền xóa phản hồi này.")
            code = fb.code
            fb.delete()
            messages.success(request, f"Đã xóa phản hồi {code}.")
            return redirect("web-inbox")

    params = request.GET.dict()
    qs = apply_feedback_filters(get_scoped_feedbacks(request.user), params, user=request.user)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    feedbacks = _mark_voted_flags(page_obj.object_list, request.user)

    query_no_page = request.GET.copy()
    query_no_page.pop("page", None)

    return render(
        request,
        "pages/inbox.html",
        {
            "active_nav": "inbox",
            "feedbacks": feedbacks,
            "page_obj": page_obj,
            "total_count": paginator.count,
            "products": Product.objects.filter(is_active=True),
            "tags": Tag.objects.all(),
            "filters": {
                "search": params.get("search", ""),
                "status": params.get("status", ""),
                "source": params.get("source", ""),
                "tag": params.get("tag", ""),
                "impact_level": params.get("impact_level", ""),
                "unclustered_only": params.get("unclustered_only", "") in ("1", "true", "on"),
                "duplicate_only": params.get("duplicate_only", "") in ("1", "true", "on"),
            },
            "querystring_no_page": query_no_page.urlencode(),
        },
    )


@web_feature_required("inbox", "kanban")
def feedback_detail_view(request, pk: int):
    fb = get_object_or_404(get_scoped_feedbacks(request.user), pk=pk)
    role = request.user.role_code
    is_internal = role in (
        Role.ADMIN,
        Role.PRODUCT_MANAGER,
        Role.DEVELOPER,
        Role.CUSTOMER_SUPPORT,
    )
    can_assign = role in (Role.ADMIN, Role.PRODUCT_MANAGER, Role.CUSTOMER_SUPPORT)

    similar_matches = []
    similarity_ran = False

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "vote":
            existing = Vote.objects.filter(user=request.user, feedback=fb).first()
            if existing:
                existing.delete()
                voted = False
            else:
                Vote.objects.create(user=request.user, feedback=fb)
                voted = True
            if is_json_request(request):
                return JsonResponse({"voted": voted, "votes_count": fb.votes.count()})
            return redirect("web-feedback-detail", pk=fb.id)

        if action == "edit_customer_feedback":
            if role != Role.CUSTOMER or fb.author_id != request.user.id or fb.status != Feedback.STATUS_NEW:
                return render_forbidden(request, "Chỉ có thể chỉnh sửa phản hồi của mình khi trạng thái là NEW.")
            serializer = FeedbackWriteSerializer(
                fb,
                data={
                    "title": request.POST.get("title", "").strip(),
                    "content": request.POST.get("content", "").strip(),
                    "impact_level": request.POST.get("impact_level", fb.impact_level),
                },
                partial=True,
            )
            try:
                serializer.is_valid(raise_exception=True)
                serializer.save()
                messages.success(request, "Đã cập nhật nội dung phản hồi.")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
            return redirect("web-feedback-detail", pk=fb.id)

        if not is_internal:
            return render_forbidden(request, "Tài khoản khách hàng không có quyền thực hiện thao tác nội bộ này.")

        if action == "update_status":
            new_status = request.POST.get("status", "")
            valid = {c[0] for c in Feedback.STATUS_CHOICES}
            if new_status not in valid:
                messages.error(request, "Trạng thái không hợp lệ.")
            elif new_status != fb.status:
                old_status = fb.status
                fb.status = new_status
                fb.save(update_fields=["status", "updated_at"])
                notify_feedback_status_changed(fb, old_status, new_status, actor=request.user)
                messages.success(request, f"Đã chuyển trạng thái sang {new_status}.")
            return redirect("web-feedback-detail", pk=fb.id)

        if action == "assign":
            if not can_assign:
                return render_forbidden(request, "Bạn không có quyền phân công người phụ trách.")
            assignee_id = request.POST.get("assigned_to", "").strip()
            assignee = None
            if assignee_id:
                assignee = User.objects.filter(id=assignee_id, is_active=True).first()
                if not assignee:
                    messages.error(request, "Người được phân công không tồn tại.")
                    return redirect("web-feedback-detail", pk=fb.id)
            old_id = fb.assigned_to_id
            fb.assigned_to = assignee
            fb.save(update_fields=["assigned_to", "updated_at"])
            if assignee and old_id != assignee.id:
                notify_feedback_assigned(fb, assignee, actor=request.user)
            messages.success(request, "Đã cập nhật người phụ trách.")
            return redirect("web-feedback-detail", pk=fb.id)

        if action == "toggle_tag":
            tag = get_object_or_404(Tag, pk=request.POST.get("tag_id"))
            link = FeedbackTag.objects.filter(feedback=fb, tag=tag).first()
            if link:
                link.delete()
            else:
                FeedbackTag.objects.create(feedback=fb, tag=tag)
            return redirect("web-feedback-detail", pk=fb.id)

        if action == "summarize":
            try:
                summarize_single_feedback(fb, use_llm=True)
                messages.success(request, "AI đã tóm tắt nội dung feedback!")
            except Exception as exc:
                logger.warning("AI summarize failed for fb=%s: %s", fb.id, exc)
                messages.error(request, f"Không thể kết nối AI Service: {exc}")
            return redirect("web-feedback-detail", pk=fb.id)

        if action == "find_similar":
            try:
                res = find_similar_feedbacks(fb, top_k=6, min_similarity=0.3)
                similar_matches = res.get("matches", [])
                similarity_ran = True
                if not similar_matches:
                    messages.info(request, "Không tìm thấy feedback tương đồng vượt ngưỡng.")
            except Exception as exc:
                logger.warning("AI similarity failed for fb=%s: %s", fb.id, exc)
                messages.error(request, f"Không thể kết nối AI Service: {exc}")

        if action == "mark_duplicate":
            if not can_assign:
                return render_forbidden(request, "Chỉ PM, Admin hoặc CS mới có quyền đánh dấu trùng lặp.")
            target_id = request.POST.get("duplicate_of_id")
            if not target_id or int(target_id) == fb.id:
                messages.error(request, "Cần chọn feedback gốc hợp lệ khác feedback hiện tại.")
            else:
                target = get_object_or_404(Feedback, pk=target_id)
                sim_raw = request.POST.get("similarity_score", "").strip()
                fb.duplicate_of = target
                if sim_raw:
                    try:
                        fb.similarity_score = float(sim_raw)
                    except ValueError:
                        pass
                fb.is_duplicate_confirmed = True
                fb.status = Feedback.STATUS_DUPLICATE
                fb.save()
                messages.success(request, "Đã xác nhận đánh dấu trùng lặp.")
            return redirect("web-feedback-detail", pk=fb.id)

        if action == "unmark_duplicate":
            fb.duplicate_of = None
            fb.similarity_score = None
            fb.is_duplicate_confirmed = False
            if fb.status == Feedback.STATUS_DUPLICATE:
                fb.status = Feedback.STATUS_NEW
            fb.save()
            messages.success(request, "Đã gỡ đánh dấu trùng lặp.")
            return redirect("web-feedback-detail", pk=fb.id)

    fb.user_has_voted = Vote.objects.filter(user=request.user, feedback=fb).exists()
    fb.votes_total = fb.votes.count()
    fb_tag_ids = set(fb.tags.values_list("id", flat=True))
    staff = (
        User.objects.select_related("role")
        .filter(is_active=True)
        .exclude(role__code=Role.CUSTOMER)
        .order_by("full_name", "username")
        if is_internal
        else []
    )
    all_tags = list(Tag.objects.all()) if is_internal else []

    return render(
        request,
        "pages/feedback_detail.html",
        {
            "active_nav": "inbox",
            "fb": fb,
            "fb_tag_ids": fb_tag_ids,
            "all_tags": all_tags,
            "staff": staff,
            "can_assign": can_assign,
            "similar_matches": similar_matches,
            "similarity_ran": similarity_ran,
            "kanban_statuses": [("NEW", "New"), ("REVIEWING", "Reviewing"), ("PLANNED", "Planned"), ("DONE", "Done")],
        },
    )


@web_feature_required("sources")
def sources_hub_view(request):
    active_tab = request.GET.get("tab") or request.POST.get("source_code") or "WEB_FORM"
    if active_tab not in ("WEB_FORM", "EMAIL", "LIVE_CHAT", "COMMUNITY"):
        active_tab = "WEB_FORM"

    if request.method == "POST":
        tag_ids = [int(x) for x in request.POST.getlist("tag_ids") if str(x).isdigit()]
        serializer = MultiSourceIngestSerializer(
            data={
                "source_code": request.POST.get("source_code", "WEB_FORM"),
                "product_id": request.POST.get("product_id") or None,
                "title": request.POST.get("title", "").strip(),
                "content": request.POST.get("content", "").strip(),
                "sender_name": request.POST.get("sender_name", "").strip(),
                "sender_email": request.POST.get("sender_email", "").strip(),
                "impact_level": request.POST.get("impact_level", Feedback.IMPACT_MEDIUM),
                "tag_ids": tag_ids,
            }
        )
        try:
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            source = FeedbackSource.objects.filter(code=data["source_code"], is_active=True).first()
            if not source:
                messages.error(request, f"Nguồn phản hồi {data['source_code']} không tồn tại hoặc đang tắt.")
                return redirect(f"/sources/?tab={active_tab}")

            product = None
            if data.get("product_id"):
                product = Product.objects.filter(id=data["product_id"], is_active=True).first()
            if not product:
                product = Product.objects.filter(is_active=True).first()
            if not product:
                messages.error(request, "Chưa có sản phẩm nào hoạt động trong hệ thống.")
                return redirect(f"/sources/?tab={active_tab}")

            sender_name = (data.get("sender_name") or "").strip() or request.user.display_name()
            sender_email = (data.get("sender_email") or "").strip() or request.user.email
            matched_author = User.objects.filter(email__iexact=sender_email).first() or request.user

            fb = Feedback.objects.create(
                title=data["title"].strip(),
                content=data["content"].strip(),
                sender_name=sender_name,
                sender_email=sender_email,
                author=matched_author,
                product=product,
                source=source,
                impact_level=data["impact_level"],
                status=Feedback.STATUS_NEW,
            )
            for tag in Tag.objects.filter(id__in=data.get("tag_ids", [])):
                FeedbackTag.objects.get_or_create(feedback=fb, tag=tag)

            notify_feedback_received(fb, actor=request.user)
            messages.success(request, f"Đã tiếp nhận {fb.code} từ kênh {source.name}!")
            return redirect("web-feedback-detail", pk=fb.id)
        except ValidationError as exc:
            messages.error(request, format_serializer_error(exc))

    products = list(Product.objects.filter(is_active=True))
    sources = list(
        FeedbackSource.objects.annotate(feedback_count=Count("feedbacks", distinct=True))
    )
    source_counts = {s.code: s.feedback_count for s in sources}
    sample_emails = [
        {
            "sender_name": "Lê Minh Hoàng",
            "sender_email": "hoang.le@gmail.com",
            "subject": "[Khẩn] Thanh toán MoMo bị trừ tiền nhưng đơn chưa lên",
            "content": "Tôi thanh toán đơn 210.000đ bằng ví MoMo lúc 12h05, ví báo đã trừ tiền nhưng app Bếp Việt Go quay vòng rồi báo giao dịch thất bại.",
            "impact_level": "CRITICAL",
        },
        {
            "sender_name": "Nguyễn Thu Trang",
            "sender_email": "trang.nguyen@yahoo.com",
            "subject": "Không nhận được thông báo khi tài xế tới cổng",
            "content": "Shipper đứng chờ 10 phút ngoài cổng gọi mới biết vì ứng dụng hoàn toàn không gửi thông báo đẩy.",
            "impact_level": "HIGH",
        },
    ]

    return render(
        request,
        "pages/sources.html",
        {
            "active_nav": "sources",
            "active_tab": active_tab,
            "products": products,
            "tags": Tag.objects.all(),
            "source_counts": source_counts,
            "sample_emails": sample_emails,
            "sample_emails_json": json.dumps(sample_emails, ensure_ascii=False),
        },
    )


@login_required
def notifications_view(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "mark_read":
            notif = get_object_or_404(Notification, pk=request.POST.get("notification_id"), recipient=request.user)
            if not notif.is_read:
                notif.is_read = True
                notif.save(update_fields=["is_read"])
            if notif.link_url:
                return redirect(notif.link_url)
            return redirect("web-notifications")
        if action == "mark_all_read":
            Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
            messages.success(request, "Đã đánh dấu tất cả thông báo là đã đọc.")
            return redirect("web-notifications")

    unread_only = request.GET.get("unread_only") in ("1", "true", "on")
    qs = Notification.objects.filter(recipient=request.user)
    if unread_only:
        qs = qs.filter(is_read=False)
    items = list(qs[:50])

    return render(
        request,
        "pages/notifications.html",
        {
            "active_nav": "notifications",
            "items": items,
            "unread_only": unread_only,
        },
    )
