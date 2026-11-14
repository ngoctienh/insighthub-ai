from typing import Any, Optional

from apps.accounts.models import Role, User
from .models import ActivityLog, Notification


def log_activity(
    actor: Optional[User],
    entity_type: str,
    entity_id: int,
    action: str,
    description: str = "",
    old_value: Any = None,
    new_value: Any = None,
) -> ActivityLog:
    return ActivityLog.objects.create(
        actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        description=description,
        old_value=old_value,
        new_value=new_value,
    )


def notify_user(
    recipient: Optional[User],
    event_type: str,
    title: str,
    message: str,
    actor: Optional[User] = None,
    feedback=None,
    insight_group=None,
    roadmap_item=None,
    link_url: str = "",
) -> Optional[Notification]:
    if not recipient or not recipient.is_active:
        return None
    if actor and recipient.id == actor.id:
        return None
    return Notification.objects.create(
        recipient=recipient,
        actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
        event_type=event_type,
        title=title[:255],
        message=message,
        feedback=feedback,
        insight_group=insight_group,
        roadmap_item=roadmap_item,
        link_url=link_url,
    )


def notify_feedback_received(feedback, actor: Optional[User] = None):
    if feedback.author_id:
        notify_user(
            recipient=feedback.author,
            event_type=Notification.EVENT_FEEDBACK_RECEIVED,
            title=f"Đã tiếp nhận phản hồi {feedback.code}",
            message=f"Phản hồi \"{feedback.title}\" đã được hệ thống ghi nhận qua kênh {feedback.source.name}.",
            actor=None,
            feedback=feedback,
            link_url=f"/inbox/{feedback.id}",
        )

    if feedback.impact_level in ("CRITICAL", "HIGH"):
        pms = User.objects.filter(
            is_active=True,
            role__code__in=[Role.PRODUCT_MANAGER, Role.ADMIN],
        )
        for pm in pms:
            notify_user(
                recipient=pm,
                event_type=Notification.EVENT_FEEDBACK_RECEIVED,
                title=f"[{feedback.impact_level}] Feedback mới: {feedback.code}",
                message=f"{feedback.sender_name} vừa gửi phản hồi \"{feedback.title}\" qua {feedback.source.name}.",
                actor=actor,
                feedback=feedback,
                link_url=f"/inbox/{feedback.id}",
            )


def notify_feedback_assigned(feedback, assignee: Optional[User], actor: Optional[User] = None):
    if assignee:
        notify_user(
            recipient=assignee,
            event_type=Notification.EVENT_FEEDBACK_ASSIGNED,
            title=f"Bạn được phân công xử lý {feedback.code}",
            message=f"Phản hồi \"{feedback.title}\" (mức ảnh hưởng: {feedback.impact_level}) đã được gán cho bạn.",
            actor=actor,
            feedback=feedback,
            link_url=f"/inbox/{feedback.id}",
        )


def notify_feedback_status_changed(feedback, old_status: str, new_status: str, actor: Optional[User] = None):
    if old_status == new_status:
        return
    is_completed = new_status == "COMPLETED"
    event_type = Notification.EVENT_ISSUE_COMPLETED if is_completed else Notification.EVENT_STATUS_CHANGED
    title = (
        f"Phản hồi {feedback.code} đã hoàn thành!"
        if is_completed
        else f"Cập nhật trạng thái {feedback.code}: {new_status}"
    )
    msg = f"Phản hồi \"{feedback.title}\" đã chuyển từ {old_status} sang {new_status}."

    recipients: dict[int, User] = {}
    if feedback.author_id:
        recipients[feedback.author_id] = feedback.author
    if feedback.assigned_to_id:
        recipients[feedback.assigned_to_id] = feedback.assigned_to

    for user in recipients.values():
        notify_user(
            recipient=user,
            event_type=event_type,
            title=title,
            message=msg,
            actor=actor,
            feedback=feedback,
            link_url=f"/inbox/{feedback.id}",
        )


def notify_insight_confirmed(insight, actor: Optional[User] = None):
    staff = User.objects.filter(
        is_active=True,
        role__code__in=[Role.PRODUCT_MANAGER, Role.DEVELOPER, Role.CUSTOMER_SUPPORT],
    )
    for member in staff:
        notify_user(
            recipient=member,
            event_type=Notification.EVENT_INSIGHT_CONFIRMED,
            title=f"Insight {insight.code} đã được xác nhận",
            message=f"Nhóm insight \"{insight.title}\" (Priority {insight.priority_score}/100 - {insight.priority_level}) đã được xác nhận.",
            actor=actor,
            insight_group=insight,
            link_url=f"/insights/{insight.id}",
        )


def notify_insight_status_changed(insight, old_status: str, new_status: str, actor: Optional[User] = None):
    if old_status == new_status:
        return
    is_completed = new_status == "COMPLETED"
    event_type = Notification.EVENT_ISSUE_COMPLETED if is_completed else Notification.EVENT_STATUS_CHANGED

    if insight.assigned_to_id:
        notify_user(
            recipient=insight.assigned_to,
            event_type=event_type,
            title=f"Insight {insight.code} chuyển sang {new_status}",
            message=f"Nhóm insight \"{insight.title}\" đã cập nhật trạng thái từ {old_status} sang {new_status}.",
            actor=actor,
            insight_group=insight,
            link_url=f"/insights/{insight.id}",
        )

    # Notify customers whose feedbacks belong to this insight on major milestones
    if new_status in ("PLANNED", "IN_PROGRESS", "COMPLETED"):
        notified_author_ids: set[int] = set()
        for link in insight.insight_feedback_links.select_related("feedback__author").all():
            fb = link.feedback
            if fb.author_id and fb.author_id not in notified_author_ids:
                notified_author_ids.add(fb.author_id)
                title = (
                    f"Vấn đề bạn phản ánh ({fb.code}) đã được hoàn thành!"
                    if is_completed
                    else f"Phản hồi {fb.code} đang tiến triển ({new_status})"
                )
                msg = (
                    f"Nhóm vấn đề \"{insight.title}\" liên quan đến phản hồi \"{fb.title}\" "
                    f"đã chuyển sang trạng thái {new_status}."
                )
                notify_user(
                    recipient=fb.author,
                    event_type=event_type,
                    title=title,
                    message=msg,
                    actor=actor,
                    feedback=fb,
                    insight_group=insight,
                    link_url=f"/inbox/{fb.id}",
                )


def notify_roadmap_updated(roadmap_item, actor: Optional[User] = None, created: bool = False):
    action_label = "tạo mới" if created else "cập nhật"
    if roadmap_item.owner_id:
        notify_user(
            recipient=roadmap_item.owner,
            event_type=Notification.EVENT_ROADMAP_UPDATED,
            title=f"Roadmap {roadmap_item.code} vừa được {action_label}",
            message=f"Hạng mục \"{roadmap_item.title}\" ({roadmap_item.status}, {roadmap_item.progress_percent}%).",
            actor=actor,
            roadmap_item=roadmap_item,
            link_url="/roadmap",
        )

    if roadmap_item.visibility == "PUBLIC":
        notified_ids: set[int] = set()
        for insight in roadmap_item.insight_groups.all():
            for link in insight.insight_feedback_links.select_related("feedback__author").all():
                fb = link.feedback
                if fb.author_id and fb.author_id not in notified_ids:
                    notified_ids.add(fb.author_id)
                    notify_user(
                        recipient=fb.author,
                        event_type=Notification.EVENT_ROADMAP_UPDATED,
                        title=f"Lộ trình sản phẩm được {action_label}: {roadmap_item.title}",
                        message=f"Đề xuất liên quan tới phản hồi {fb.code} hiện đang ở trạng thái {roadmap_item.status} ({roadmap_item.quarter}).",
                        actor=actor,
                        feedback=fb,
                        roadmap_item=roadmap_item,
                        link_url="/public-roadmap",
                    )
