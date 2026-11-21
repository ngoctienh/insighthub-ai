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


class Notification(models.Model):
    EVENT_FEEDBACK_RECEIVED = "FEEDBACK_RECEIVED"
    EVENT_FEEDBACK_ASSIGNED = "FEEDBACK_ASSIGNED"
    EVENT_FEEDBACK_REPLIED = "FEEDBACK_REPLIED"
    EVENT_STATUS_CHANGED = "STATUS_CHANGED"
    EVENT_INSIGHT_CONFIRMED = "INSIGHT_CONFIRMED"
    EVENT_ROADMAP_UPDATED = "ROADMAP_UPDATED"
    EVENT_ISSUE_COMPLETED = "ISSUE_COMPLETED"

    EVENT_CHOICES = [
        (EVENT_FEEDBACK_RECEIVED, "Feedback Received"),
        (EVENT_FEEDBACK_ASSIGNED, "Feedback Assigned"),
        (EVENT_FEEDBACK_REPLIED, "Feedback Replied"),
        (EVENT_STATUS_CHANGED, "Status Changed"),
        (EVENT_INSIGHT_CONFIRMED, "Insight Confirmed"),
        (EVENT_ROADMAP_UPDATED, "Roadmap Updated"),
        (EVENT_ISSUE_COMPLETED, "Issue Completed"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
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
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]

    @property
    def link_url(self) -> str:
        if self.feedback_id:
            return f"/inbox/{self.feedback_id}/"
        if self.event_type == self.EVENT_ROADMAP_UPDATED:
            return "/public-roadmap/"
        if self.event_type in (self.EVENT_INSIGHT_CONFIRMED, self.EVENT_STATUS_CHANGED):
            return "/insights/"
        return ""
