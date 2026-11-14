from django.conf import settings
from django.db import models


class InsightGroup(models.Model):
    STATUS_NEW = "NEW"
    STATUS_ANALYZING = "ANALYZING"
    STATUS_PLANNED = "PLANNED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"

    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_ANALYZING, "Analyzing"),
        (STATUS_PLANNED, "Planned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
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
    user_impact = models.TextField(blank=True, default="")
    ai_recommendations = models.JSONField(default=list, blank=True)
    draft_customer_reply = models.TextField(blank=True, default="")
    analysis_mode = models.CharField(max_length=32, default="local_nlp")
    ai_confidence = models.FloatField(default=0.75)

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
    priority_reasoning = models.TextField(blank=True, default="")
    is_priority_overridden = models.BooleanField(default=False)
    pm_priority_notes = models.TextField(blank=True, default="")

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
    affected_customers_count = models.PositiveIntegerField(default=0)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_insights",
    )
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_insights",
    )
    feedbacks = models.ManyToManyField(
        "feedbacks.Feedback",
        through="InsightFeedback",
        related_name="insight_groups",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    def sync_counts(self):
        links = self.insight_feedback_links.select_related("feedback").all()
        emails = {
            (link.feedback.sender_email or f"id:{link.feedback_id}").strip().lower()
            for link in links
        }
        self.feedback_count = links.count()
        self.affected_customers_count = len(emails)
        InsightGroup.objects.filter(pk=self.pk).update(
            feedback_count=self.feedback_count,
            affected_customers_count=self.affected_customers_count,
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
    added_by_ai = models.BooleanField(default=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manual_insight_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "insight_feedbacks"
        constraints = [
            models.UniqueConstraint(
                fields=["insight_group", "feedback"],
                name="unique_insight_feedback",
            )
        ]


class AIAnalysisJob(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_RUNNING = "RUNNING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    product = models.ForeignKey(
        "feedbacks.Product",
        on_delete=models.CASCADE,
        related_name="ai_jobs",
        null=True,
        blank=True,
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_ai_jobs",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    config = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    duplicate_candidates = models.JSONField(default=list, blank=True)
    unassigned_feedback_ids = models.JSONField(default=list, blank=True)
    analysis_mode = models.CharField(max_length=32, default="local_nlp")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_analysis_jobs"
        ordering = ["-created_at"]
