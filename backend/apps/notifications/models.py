from django.conf import settings
from django.db import models


class Vote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    feedback = models.ForeignKey(
        "feedbacks.Feedback",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="votes",
    )
    insight_group = models.ForeignKey(
        "insights.InsightGroup",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="votes",
    )
    weight = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "votes"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "feedback"],
                condition=models.Q(feedback__isnull=False),
                name="unique_user_feedback_vote",
            ),
            models.UniqueConstraint(
                fields=["user", "insight_group"],
                condition=models.Q(insight_group__isnull=False),
                name="unique_user_insight_vote",
            ),
        ]


class Comment(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    feedback = models.ForeignKey(
        "feedbacks.Feedback",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comments",
    )
    insight_group = models.ForeignKey(
        "insights.InsightGroup",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comments",
    )
    roadmap_item = models.ForeignKey(
        "roadmap.RoadmapItem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comments",
    )
    content = models.TextField()
    is_internal = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comments"
        ordering = ["created_at"]


class Notification(models.Model):
    EVENT_FEEDBACK_RECEIVED = "FEEDBACK_RECEIVED"
    EVENT_FEEDBACK_ASSIGNED = "FEEDBACK_ASSIGNED"
    EVENT_STATUS_CHANGED = "STATUS_CHANGED"
    EVENT_INSIGHT_CONFIRMED = "INSIGHT_CONFIRMED"
    EVENT_ROADMAP_UPDATED = "ROADMAP_UPDATED"
    EVENT_ISSUE_COMPLETED = "ISSUE_COMPLETED"
    EVENT_COMMENT_ADDED = "COMMENT_ADDED"

    EVENT_CHOICES = [
        (EVENT_FEEDBACK_RECEIVED, "Feedback Received"),
        (EVENT_FEEDBACK_ASSIGNED, "Feedback Assigned"),
        (EVENT_STATUS_CHANGED, "Status Changed"),
        (EVENT_INSIGHT_CONFIRMED, "Insight Confirmed"),
        (EVENT_ROADMAP_UPDATED, "Roadmap Updated"),
        (EVENT_ISSUE_COMPLETED, "Issue Completed"),
        (EVENT_COMMENT_ADDED, "Comment Added"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    feedback = models.ForeignKey(
        "feedbacks.Feedback",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    insight_group = models.ForeignKey(
        "insights.InsightGroup",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    roadmap_item = models.ForeignKey(
        "roadmap.RoadmapItem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    link_url = models.CharField(max_length=255, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]


class ActivityLog(models.Model):
    ENTITY_FEEDBACK = "FEEDBACK"
    ENTITY_INSIGHT = "INSIGHT"
    ENTITY_ROADMAP = "ROADMAP"
    ENTITY_USER = "USER"
    ENTITY_AI_JOB = "AI_JOB"

    ENTITY_CHOICES = [
        (ENTITY_FEEDBACK, "Feedback"),
        (ENTITY_INSIGHT, "Insight"),
        (ENTITY_ROADMAP, "Roadmap"),
        (ENTITY_USER, "User"),
        (ENTITY_AI_JOB, "AI Job"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    entity_type = models.CharField(max_length=24, choices=ENTITY_CHOICES, db_index=True)
    entity_id = models.BigIntegerField(db_index=True)
    action = models.CharField(max_length=64)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "created_at"]),
        ]
