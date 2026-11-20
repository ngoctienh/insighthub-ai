from django.conf import settings
from django.db import models


class InsightGroup(models.Model):
    STATUS_NEW = "NEW"
    STATUS_REVIEWING = "REVIEWING"
    STATUS_PLANNED = "PLANNED"
    STATUS_DONE = "DONE"

    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_REVIEWING, "Reviewing"),
        (STATUS_PLANNED, "Planned"),
        (STATUS_DONE, "Done"),
    ]

    VERIFY_PENDING = "PENDING_REVIEW"
    VERIFY_CONFIRMED = "CONFIRMED"
    VERIFY_REJECTED = "REJECTED"

    VERIFICATION_CHOICES = [
        (VERIFY_PENDING, "Pending Review"),
        (VERIFY_CONFIRMED, "Confirmed"),
        (VERIFY_REJECTED, "Rejected"),
    ]

    PRIORITY_CRITICAL = "CRITICAL"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_LOW = "LOW"

    PRIORITY_CHOICES = [
        (PRIORITY_CRITICAL, "Critical"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_LOW, "Low"),
    ]

    code = models.CharField(max_length=24, unique=True, blank=True)
    product = models.ForeignKey(
        "feedbacks.Product",
        on_delete=models.CASCADE,
        related_name="insight_groups",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    possible_causes = models.JSONField(default=list, blank=True)
    ai_recommendations = models.JSONField(default=list, blank=True)
    draft_customer_reply = models.TextField(blank=True, default="")

    volume_score = models.FloatField(default=0.0)
    impact_score = models.FloatField(default=0.0)
    severity_score = models.FloatField(default=0.0)
    priority_score = models.FloatField(default=0.0, db_index=True)
    priority_level = models.CharField(
        max_length=16,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        db_index=True,
    )

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
        db_index=True,
    )
    verification_status = models.CharField(
        max_length=24,
        choices=VERIFICATION_CHOICES,
        default=VERIFY_PENDING,
        db_index=True,
    )

    feedback_count = models.PositiveIntegerField(default=0)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_insights",
    )
    feedbacks = models.ManyToManyField(
        "feedbacks.Feedback",
        through="InsightFeedback",
        related_name="insight_groups",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "insight_groups"
        ordering = ["-priority_score", "-created_at"]
        indexes = [
            models.Index(fields=["product", "status"]),
            models.Index(fields=["verification_status", "priority_score"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"INS-{self.id:03d}"
            InsightGroup.objects.filter(pk=self.pk).update(code=self.code)

    @property
    def affected_customers_count(self) -> int:
        links = self.insight_feedback_links.select_related("feedback").all()
        emails = {
            (link.feedback.sender_email or f"id:{link.feedback_id}").strip().lower()
            for link in links
        }
        return len(emails)

    @property
    def priority_reasoning(self) -> str:
        return (
            f"Điểm ưu tiên {self.priority_score}/100 ({self.priority_level}) = "
            f"0.40×V({self.volume_score}) + 0.35×I({self.impact_score}) + 0.25×S({self.severity_score})."
        )

    def sync_counts(self):
        self.feedback_count = self.insight_feedback_links.count()
        InsightGroup.objects.filter(pk=self.pk).update(
            feedback_count=self.feedback_count,
        )

    def __str__(self) -> str:
        return f"{self.code or self.id} - {self.title}"


class InsightFeedback(models.Model):
    insight_group = models.ForeignKey(
        InsightGroup,
        on_delete=models.CASCADE,
        related_name="insight_feedback_links",
    )
    feedback = models.ForeignKey(
        "feedbacks.Feedback",
        on_delete=models.CASCADE,
        related_name="insight_links",
    )
    similarity_to_centroid = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "insight_feedbacks"
        constraints = [
            models.UniqueConstraint(
                fields=["insight_group", "feedback"],
                name="unique_insight_feedback",
            )
        ]
