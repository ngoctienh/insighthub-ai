import json
import logging

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role, User
from apps.accounts.permissions import has_feature
from apps.feedbacks.models import Feedback, Product
from apps.insights.models import InsightFeedback, InsightGroup
from apps.insights.serializers import RunAIPipelineSerializer
from apps.insights.services import (
    classify_priority_level,
    execute_ai_pipeline,
    get_ai_task_status,
    get_duplicate_candidates_list,
    get_scoped_insights,
    get_unassigned_feedbacks_queryset,
    merge_insights,
    move_insight_kanban,
    regenerate_insight_reply,
    rescore_and_summarize_insight,
    split_insight,
)
from apps.insights.tasks import run_ai_pipeline_task
from apps.notifications.models import Vote
from apps.notifications.services import (
    notify_feedback_status_changed,
    notify_insight_confirmed,
    notify_roadmap_updated,
)
from apps.roadmap.serializers import RoadmapItemSerializer
from apps.web.decorators import is_json_request, render_forbidden, web_feature_required
from .helpers import format_serializer_error

logger = logging.getLogger(__name__)


def _annotate_insight_votes(insights, user):
    items = list(insights)
    ids = [ins.id for ins in items]
    voted_ids = set(
        Vote.objects.filter(user=user, insight_group_id__in=ids).values_list("insight_group_id", flat=True)
    )
    for ins in items:
        ins.user_has_voted = ins.id in voted_ids
        ins.votes_total = ins.votes.count()
    return items


@web_feature_required("insights")
def insights_view(request):
    role = request.user.role_code
    can_manage = role in (Role.ADMIN, Role.PRODUCT_MANAGER)
    can_run_ai = has_feature(request.user, "ai_run")
    active_tab = request.GET.get("tab") or request.POST.get("tab") or "insights"
    if active_tab not in ("insights", "duplicates", "unassigned"):
        active_tab = "insights"

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "run_ai":
            if not can_run_ai:
                return render_forbidden(request, "Vai trò của bạn chưa được cấp quyền chạy AI Engine.")
            if is_json_request(request):
                try:
                    raw = json.loads(request.body.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    raw = {}
            else:
                raw = {
                    "product_id": request.POST.get("product_id") or None,
                    "similarity_threshold": request.POST.get("similarity_threshold", 0.72),
                    "eps": request.POST.get("eps", 0.48),
                    "min_samples": request.POST.get("min_samples", 2),
                    "use_llm": request.POST.get("use_llm") in ("1", "true", "on", True),
                    "include_clustered": request.POST.get("include_clustered") in ("1", "true", "on", True),
                }
            serializer = RunAIPipelineSerializer(data=raw)
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as exc:
                err_msg = format_serializer_error(exc)
                if is_json_request(request):
                    return JsonResponse({"detail": err_msg}, status=400)
                messages.error(request, err_msg)
                return redirect("web-insights")

            cfg = serializer.validated_data
            product_id = cfg.get("product_id")
            pipeline_cfg = {
                "similarity_threshold": cfg["similarity_threshold"],
                "eps": cfg["eps"],
                "min_samples": cfg["min_samples"],
                "use_llm": cfg["use_llm"],
                "include_clustered": cfg["include_clustered"],
            }
            if settings.CELERY_ENABLED:
                task = run_ai_pipeline_task.delay(config=pipeline_cfg, product_id=product_id)
                if is_json_request(request):
                    return JsonResponse({"status": "QUEUED", "task_id": str(task.id)}, status=202)
                return redirect(f"/insights/?task_id={task.id}")

            try:
                result = execute_ai_pipeline(config=pipeline_cfg, product_id=product_id)
                if is_json_request(request):
                    return JsonResponse(result)
                metrics = result.get("metrics", {})
                messages.success(
                    request,
                    f"AI hoàn tất ({result.get('analysis_mode', 'local_nlp')}): xử lý "
                    f"{metrics.get('processed_count', 0)} feedback, tạo "
                    f"{len(metrics.get('created_insight_ids', []))} nhóm insight.",
                )
            except Exception as exc:
                logger.exception("Web AI pipeline execution failed: %s", exc)
                err_msg = f"Lỗi khi gọi AI Service tại {settings.AI_SERVICE_URL}: {exc}"
                if is_json_request(request):
                    return JsonResponse({"detail": err_msg}, status=503)
                messages.error(request, err_msg)
            return redirect("web-insights")

        if action == "vote":
            ins = get_object_or_404(get_scoped_insights(request.user), pk=request.POST.get("insight_id"))
            existing = Vote.objects.filter(user=request.user, insight_group=ins).first()
            if existing:
                existing.delete()
                voted = False
            else:
                Vote.objects.create(user=request.user, insight_group=ins)
                voted = True
            if is_json_request(request):
                return JsonResponse({"voted": voted, "votes_count": ins.votes.count()})
            return redirect("web-insights")

        if not can_manage:
            return render_forbidden(request, "Chỉ PM hoặc Admin mới có quyền quản trị nhóm Insight.")

        if action == "confirm":
            ins = get_object_or_404(InsightGroup, pk=request.POST.get("insight_id"))
            ins.verification_status = InsightGroup.VERIFY_CONFIRMED
            if ins.status == InsightGroup.STATUS_NEW:
                ins.status = InsightGroup.STATUS_REVIEWING
            ins.save(update_fields=["verification_status", "status"])
            notify_insight_confirmed(ins, actor=request.user)
            messages.success(request, f"Đã xác nhận nhóm Insight {ins.code}.")
            return redirect("web-insights")

        if action == "reject":
            ins = get_object_or_404(InsightGroup, pk=request.POST.get("insight_id"))
            ins.verification_status = InsightGroup.VERIFY_REJECTED
            ins.save(update_fields=["verification_status"])
            messages.info(request, f"Đã từ chối nhóm Insight {ins.code}.")
            return redirect("web-insights")

        if action == "confirm_duplicate":
            target = get_object_or_404(Feedback, pk=request.POST.get("feedback_a_id"))
            dup = get_object_or_404(Feedback, pk=request.POST.get("feedback_b_id"))
            if target.id != dup.id:
                dup.duplicate_of = target
                dup.is_duplicate_confirmed = True
                dup.status = Feedback.STATUS_DUPLICATE
                sim_raw = request.POST.get("similarity_score", "").strip()
                if sim_raw:
                    try:
                        dup.similarity_score = float(sim_raw)
                    except ValueError:
                        pass
                dup.save()
                messages.success(request, f"Đã xác nhận {dup.code} trùng với {target.code}.")
            return redirect("/insights/?tab=duplicates")

        if action == "dismiss_duplicate":
            fb = get_object_or_404(Feedback, pk=request.POST.get("feedback_b_id"))
            fb.duplicate_of = None
            fb.similarity_score = None
            fb.is_duplicate_confirmed = False
            if fb.status == Feedback.STATUS_DUPLICATE:
                fb.status = Feedback.STATUS_NEW
            fb.save()
            messages.info(request, f"Đã bỏ qua gợi ý trùng lặp cho {fb.code}.")
            return redirect("/insights/?tab=duplicates")

        if action == "create_manual":
            title = request.POST.get("title", "").strip()
            product_id = request.POST.get("product_id")
            fb_ids = [int(x) for x in request.POST.getlist("feedback_ids") if str(x).isdigit()]
            if not title or not fb_ids:
                messages.error(request, "Cần nhập tên nhóm Insight và chọn ít nhất 1 feedback.")
                return redirect("/insights/?tab=unassigned")

            product = Product.objects.filter(id=product_id, is_active=True).first()
            if not product:
                first_fb = Feedback.objects.filter(id__in=fb_ids).select_related("product").first()
                product = first_fb.product if first_fb else Product.objects.filter(is_active=True).first()

            insight = InsightGroup.objects.create(
                product=product,
                title=title[:255],
                verification_status=InsightGroup.VERIFY_CONFIRMED,
            )
            for fb in Feedback.objects.filter(id__in=fb_ids):
                InsightFeedback.objects.get_or_create(insight_group=insight, feedback=fb)
            rescore_and_summarize_insight(insight, use_llm=False, preserve_title=True)
            messages.success(request, f"Đã tạo nhóm Insight thủ công {insight.code}!")
            return redirect("web-insight-detail", pk=insight.id)

    insights = _annotate_insight_votes(get_scoped_insights(request.user)[:100], request.user)
    duplicates = get_duplicate_candidates_list()
    unassigned = list(get_unassigned_feedbacks_queryset()[:100])
    products = list(Product.objects.filter(is_active=True))
    queued_task_id = request.GET.get("task_id", "").strip()

    return render(
        request,
        "pages/insights.html",
        {
            "active_nav": "insights",
            "active_tab": active_tab,
            "insights": insights,
            "duplicates": duplicates,
            "unassigned": unassigned,
            "products": products,
            "can_manage": can_manage,
            "can_run_ai": can_run_ai,
            "queued_task_id": queued_task_id,
        },
    )


@web_feature_required("ai_run", "insights")
def ai_task_status_view(request, task_id: str):
    return JsonResponse(get_ai_task_status(task_id))


@web_feature_required("insights")
def insight_detail_view(request, pk: int):
    insight = get_object_or_404(get_scoped_insights(request.user), pk=pk)
    role = request.user.role_code
    can_manage = role in (Role.ADMIN, Role.PRODUCT_MANAGER)

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "vote":
            existing = Vote.objects.filter(user=request.user, insight_group=insight).first()
            if existing:
                existing.delete()
                voted = False
            else:
                Vote.objects.create(user=request.user, insight_group=insight)
                voted = True
            if is_json_request(request):
                return JsonResponse({"voted": voted, "votes_count": insight.votes.count()})
            return redirect("web-insight-detail", pk=insight.id)

        if action == "regenerate_reply":
            tone = request.POST.get("tone", "empathetic")
            try:
                regenerate_insight_reply(insight, tone=tone, use_llm=True)
                messages.success(request, "Đã tạo nháp phản hồi mới!")
            except Exception as exc:
                logger.warning("Regenerate reply failed for insight=%s: %s", insight.id, exc)
                messages.error(request, f"Không thể gọi AI Service để tạo nháp phản hồi: {exc}")
            return redirect("web-insight-detail", pk=insight.id)

        if action == "move_kanban":
            if not can_manage and insight.assigned_to_id != request.user.id:
                return render_forbidden(
                    request,
                    "Bạn chỉ có thể cập nhật Kanban cho insight được phân công cho mình.",
                )
            new_status = request.POST.get("status", "").strip()
            valid_statuses = {c[0] for c in InsightGroup.STATUS_CHOICES}
            if new_status and new_status not in valid_statuses:
                messages.error(request, "Trạng thái Kanban không hợp lệ.")
                return redirect("web-insight-detail", pk=insight.id)

            update_assignee = can_manage and "assigned_to" in request.POST
            assignee = None
            if update_assignee:
                aid = request.POST.get("assigned_to", "").strip()
                assignee = User.objects.filter(id=aid, is_active=True).first() if aid else None

            move_insight_kanban(
                insight,
                actor=request.user,
                new_status=new_status or None,
                assignee=assignee,
                update_assignee=update_assignee,
            )
            messages.success(request, "Đã cập nhật Kanban & phân công.")
            return redirect("web-insight-detail", pk=insight.id)

        if not can_manage:
            return render_forbidden(request, "Chỉ PM hoặc Admin mới có quyền chỉnh sửa nhóm insight.")

        if action == "confirm":
            insight.verification_status = InsightGroup.VERIFY_CONFIRMED
            if insight.status == InsightGroup.STATUS_NEW:
                insight.status = InsightGroup.STATUS_REVIEWING
            insight.save(update_fields=["verification_status", "status"])
            notify_insight_confirmed(insight, actor=request.user)
            messages.success(request, "Đã xác nhận nhóm Insight.")
            return redirect("web-insight-detail", pk=insight.id)

        if action == "reject":
            insight.verification_status = InsightGroup.VERIFY_REJECTED
            insight.save(update_fields=["verification_status"])
            messages.info(request, "Đã từ chối nhóm Insight.")
            return redirect("web-insight-detail", pk=insight.id)

        if action == "edit_insight":
            title = request.POST.get("title", "").strip()
            description = request.POST.get("description", "").strip()
            score_raw = request.POST.get("priority_score", "").strip()
            if title:
                insight.title = title[:255]
            if description:
                insight.description = description
            if score_raw:
                try:
                    score = max(0.0, min(100.0, round(float(score_raw), 1)))
                    insight.priority_score = score
                    insight.priority_level = classify_priority_level(score)
                except ValueError:
                    messages.error(request, "Điểm ưu tiên phải là số từ 0 đến 100.")
                    return redirect("web-insight-detail", pk=insight.id)
            insight.save()
            messages.success(request, "Đã cập nhật thông tin & mức ưu tiên của Insight.")
            return redirect("web-insight-detail", pk=insight.id)

        if action == "merge":
            source_id = request.POST.get("source_insight_id")
            if not source_id or int(source_id) == insight.id:
                messages.error(request, "Cần chọn nhóm insight nguồn khác nhóm hiện tại.")
            else:
                source = get_object_or_404(InsightGroup, pk=source_id)
                merge_insights(insight, source)
                messages.success(request, "Đã gộp nhóm insight thành công!")
            return redirect("web-insight-detail", pk=insight.id)

        if action == "split":
            fb_ids = [int(x) for x in request.POST.getlist("feedback_ids") if str(x).isdigit()]
            new_title = request.POST.get("new_title", "").strip() or f"Nhóm tách từ {insight.code}"
            links = list(InsightFeedback.objects.filter(insight_group=insight, feedback_id__in=fb_ids))
            if not links:
                messages.error(request, "Cần chọn ít nhất 1 feedback hợp lệ để tách nhóm.")
            else:
                new_group = split_insight(insight, links, new_title)
                messages.success(request, f"Đã tách sang nhóm mới {new_group.code}!")
            return redirect("web-insight-detail", pk=insight.id)

        if action == "remove_feedback":
            fb_id = request.POST.get("feedback_id")
            deleted, _ = InsightFeedback.objects.filter(insight_group=insight, feedback_id=fb_id).delete()
            if deleted:
                rescore_and_summarize_insight(insight, use_llm=False, preserve_title=True)
                messages.info(request, "Đã gỡ feedback khỏi nhóm.")
            return redirect("web-insight-detail", pk=insight.id)

        if action == "promote_roadmap":
            serializer = RoadmapItemSerializer(
                data={
                    "product": insight.product_id,
                    "owner": insight.assigned_to_id,
                    "title": request.POST.get("title", "").strip(),
                    "description": request.POST.get("description", "").strip(),
                    "public_description": request.POST.get("public_description", "").strip(),
                    "status": request.POST.get("status", "PLANNED"),
                    "visibility": request.POST.get("visibility", "PUBLIC"),
                    "quarter": request.POST.get("quarter", "Q1 2027").strip(),
                    "progress_percent": int(request.POST.get("progress_percent", 10) or 10),
                    "insight_group_ids": [insight.id],
                }
            )
            try:
                serializer.is_valid(raise_exception=True)
                item = serializer.save()
                notify_roadmap_updated(item, actor=request.user, created=True)
                messages.success(request, f"Đã tạo Roadmap Item {item.code} từ Insight!")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
            return redirect("web-insight-detail", pk=insight.id)

    members = list(insight.insight_feedback_links.select_related("feedback__source").all())
    other_insights = list(InsightGroup.objects.exclude(id=insight.id).order_by("-priority_score")[:100])
    staff = (
        User.objects.select_related("role")
        .filter(is_active=True)
        .exclude(role__code=Role.CUSTOMER)
        .order_by("full_name", "username")
    )
    insight.user_has_voted = Vote.objects.filter(user=request.user, insight_group=insight).exists()
    insight.votes_total = insight.votes.count()

    return render(
        request,
        "pages/insight_detail.html",
        {
            "active_nav": "insights",
            "insight": insight,
            "members": members,
            "other_insights": other_insights,
            "staff": staff,
            "can_manage": can_manage,
            "roadmap_items": list(insight.roadmap_items.all()),
        },
    )


@web_feature_required("kanban")
def kanban_view(request):
    role = request.user.role_code
    is_pm_or_admin = role in (Role.ADMIN, Role.PRODUCT_MANAGER)
    mode = request.GET.get("mode") or request.POST.get("mode") or "insights"
    if mode not in ("insights", "feedbacks"):
        mode = "insights"

    if request.method == "POST":
        if is_json_request(request):
            try:
                body = json.loads(request.body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return JsonResponse({"detail": "JSON không hợp lệ."}, status=400)
            action = body.get("action", "")
            item_id = body.get("item_id")
            new_status = body.get("status")
            assignee_raw = body.get("assigned_to")
            has_assignee = "assigned_to" in body
        else:
            action = request.POST.get("action", "")
            item_id = request.POST.get("item_id")
            new_status = request.POST.get("status")
            assignee_raw = request.POST.get("assigned_to")
            has_assignee = "assigned_to" in request.POST

        if action == "move_insight":
            insight = get_object_or_404(get_scoped_insights(request.user), pk=item_id)
            if not is_pm_or_admin and insight.assigned_to_id != request.user.id:
                msg = "Bạn chỉ có thể cập nhật Kanban cho insight được phân công cho mình."
                return render_forbidden(request, msg)

            valid_statuses = {c[0] for c in InsightGroup.STATUS_CHOICES}
            if new_status and new_status not in valid_statuses:
                if is_json_request(request):
                    return JsonResponse({"detail": "Trạng thái Kanban không hợp lệ."}, status=400)
                messages.error(request, "Trạng thái Kanban không hợp lệ.")
                return redirect(f"/kanban/?mode={mode}")

            update_assignee = has_assignee and is_pm_or_admin
            assignee = None
            if update_assignee and assignee_raw:
                assignee = User.objects.filter(id=assignee_raw, is_active=True).first()

            move_insight_kanban(
                insight,
                actor=request.user,
                new_status=new_status or None,
                assignee=assignee,
                update_assignee=update_assignee,
            )
            if is_json_request(request):
                return JsonResponse(
                    {
                        "id": insight.id,
                        "code": insight.code,
                        "status": insight.status,
                        "assigned_to": insight.assigned_to_id,
                        "assigned_to_name": insight.assigned_to.display_name() if insight.assigned_to else "Chưa gán",
                    }
                )
            messages.success(request, f"Đã cập nhật {insight.code} sang {insight.status}.")
            return redirect("/kanban/?mode=insights")

        if action == "move_feedback":
            from apps.feedbacks.services import get_scoped_feedbacks

            fb = get_object_or_404(get_scoped_feedbacks(request.user), pk=item_id)
            if role == Role.CUSTOMER:
                return render_forbidden(request, "Khách hàng không có quyền chuyển trạng thái Kanban.")
            valid_statuses = {c[0] for c in InsightGroup.STATUS_CHOICES}
            if new_status not in valid_statuses:
                if is_json_request(request):
                    return JsonResponse({"detail": "Trạng thái Kanban không hợp lệ."}, status=400)
                messages.error(request, "Trạng thái Kanban không hợp lệ.")
                return redirect("/kanban/?mode=feedbacks")

            old_status = fb.status
            if old_status != new_status:
                fb.status = new_status
                fb.save(update_fields=["status", "updated_at"])
                notify_feedback_status_changed(fb, old_status, new_status, actor=request.user)
            if is_json_request(request):
                return JsonResponse({"id": fb.id, "code": fb.code, "status": fb.status})
            messages.success(request, f"Đã chuyển {fb.code} sang {fb.status}.")
            return redirect("/kanban/?mode=feedbacks")

    from apps.feedbacks.services import get_scoped_feedbacks

    insights = list(
        get_scoped_insights(request.user)
        .exclude(verification_status=InsightGroup.VERIFY_REJECTED)[:100]
    )
    feedbacks = list(
        get_scoped_feedbacks(request.user)
        .exclude(status=Feedback.STATUS_DUPLICATE)[:100]
    )
    staff = list(
        User.objects.select_related("role")
        .filter(is_active=True)
        .exclude(role__code=Role.CUSTOMER)
        .order_by("full_name", "username")
    )

    columns = [
        {"key": "NEW", "label": "New", "dot": "bg-sky-500", "next": "REVIEWING"},
        {"key": "REVIEWING", "label": "Reviewing", "dot": "bg-violet-500", "next": "PLANNED"},
        {"key": "PLANNED", "label": "Planned", "dot": "bg-amber-500", "next": "DONE"},
        {"key": "DONE", "label": "Done", "dot": "bg-emerald-500", "next": None},
    ]
    for col in columns:
        col["insights"] = [i for i in insights if i.status == col["key"]]
        col["feedbacks"] = [f for f in feedbacks if f.status == col["key"]]

    insights_payload = {
        str(ins.id): {
            "id": ins.id,
            "code": ins.code,
            "title": ins.title,
            "description": ins.description,
            "status": ins.status,
            "priority_level": ins.priority_level,
            "priority_score": ins.priority_score,
            "assigned_to": ins.assigned_to_id or "",
        }
        for ins in insights
    }

    return render(
        request,
        "pages/kanban.html",
        {
            "active_nav": "kanban",
            "mode": mode,
            "columns": columns,
            "insights_count": len(insights),
            "feedbacks_count": len(feedbacks),
            "staff": staff,
            "is_pm_or_admin": is_pm_or_admin,
            "insights_payload": insights_payload,
        },
    )
