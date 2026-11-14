from django.conf import settings
from django.db import models


class RoadmapItem(models.Model):
    STATUS_PLANNED = "PLANNED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"

    STATUS_CHOICES = [
        (STATUS_PLANNED, "Planned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    VISIBILITY_PUBLIC = "PUBLIC"
    VISIBILITY_PRIVATE = "PRIVATE"

    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, "Public"),
        (VISIBILITY_PRIVATE, "Private"),
    ]

    code = models.CharField(max_length=24, unique=True, blank=True)
    product = models.ForeignKey(
        "feedbacks.Product",
        on_delete=models.CASCADE,
        related_name="roadmap_items",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    public_description = models.TextField(blank=True, default="")
    internal_notes = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_PLANNED,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=16,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PUBLIC,
        db_index=True,
    )
    quarter = models.CharField(max_length=32, blank=True, default="Q4 2026")
    target_start_date = models.DateField(null=True, blank=True)
    target_end_date = models.DateField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_roadmap_items",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_roadmap_items",
    )
    insight_groups = models.ManyToManyField(
        "insights.InsightGroup",
        through="RoadmapItemInsight",
        related_name="roadmap_items",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "roadmap_items"
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["visibility", "status"]),
            models.Index(fields=["product", "status"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"RM-{self.id:03d}"
            RoadmapItem.objects.filter(pk=self.pk).update(code=self.code)

    def __str__(self) -> str:
        return f"{self.code or self.id} - {self.title}"


class RoadmapItemInsight(models.Model):
    roadmap_item = models.ForeignKey(
        RoadmapItem,
        on_delete=models.CASCADE,
        related_name="roadmap_insight_links",
    )
    insight_group = models.ForeignKey(
        "insights.InsightGroup",
        on_delete=models.CASCADE,
        related_name="insight_roadmap_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "roadmap_item_insights"
        constraints = [
            models.UniqueConstraint(
                fields=["roadmap_item", "insight_group"],
                name="unique_roadmap_insight",
            )
        ]
