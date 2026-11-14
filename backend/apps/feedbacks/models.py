from django.conf import settings
from django.db import models
from django.utils import timezone


class Product(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=100, blank=True, default="SaaS / Mobile App")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_products",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class FeedbackSource(models.Model):
    WEB_FORM = "WEB_FORM"
    EMAIL = "EMAIL"
    LIVE_CHAT = "LIVE_CHAT"
    COMMUNITY = "COMMUNITY"

    SOURCE_CHOICES = [
        (WEB_FORM, "Website Form"),
        (EMAIL, "Email"),
        (LIVE_CHAT, "Live Chat"),
        (COMMUNITY, "Community Forum"),
    ]

    code = models.CharField(max_length=32, unique=True, choices=SOURCE_CHOICES)
    name = models.CharField(max_length=100)
    channel_type = models.CharField(max_length=50, default="WEB")
    description = models.TextField(blank=True, default="")
    webhook_token = models.CharField(max_length=128, blank=True, default="", db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedback_sources"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)
    color = models.CharField(max_length=20, default="#6366F1")
    description = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Feedback(models.Model):
    STATUS_NEW = "NEW"
    STATUS_TRIAGING = "TRIAGING"
    STATUS_ANALYZING = "ANALYZING"
    STATUS_PLANNED = "PLANNED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CLOSED = "CLOSED"
    STATUS_DUPLICATE = "DUPLICATE"

    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_TRIAGING, "Triaging"),
        (STATUS_ANALYZING, "Analyzing"),
        (STATUS_PLANNED, "Planned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_DUPLICATE, "Duplicate"),
    ]

    IMPACT_LOW = "LOW"
    IMPACT_MEDIUM = "MEDIUM"
    IMPACT_HIGH = "HIGH"
    IMPACT_CRITICAL = "CRITICAL"

    IMPACT_CHOICES = [
        (IMPACT_LOW, "Low"),
        (IMPACT_MEDIUM, "Medium"),
        (IMPACT_HIGH, "High"),
        (IMPACT_CRITICAL, "Critical"),
    ]

    code = models.CharField(max_length=24, unique=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    normalized_content = models.TextField(blank=True, default="")
    embedding = models.JSONField(null=True, blank=True)
    embedding_model = models.CharField(max_length=100, blank=True, default="")

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_feedbacks",
    )
    sender_name = models.CharField(max_length=150)
    sender_email = models.EmailField(db_index=True)

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )
    source = models.ForeignKey(
        FeedbackSource,
        on_delete=models.PROTECT,
        related_name="feedbacks",
    )
    external_reference_id = models.CharField(max_length=150, blank=True, default="")
    source_metadata = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
        db_index=True,
    )
    impact_level = models.CharField(
        max_length=16,
        choices=IMPACT_CHOICES,
        default=IMPACT_MEDIUM,
        db_index=True,
    )
    priority_score = models.FloatField(null=True, blank=True, db_index=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_feedbacks",
    )
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )
    similarity_score = models.FloatField(null=True, blank=True)
    is_duplicate_confirmed = models.BooleanField(default=False)

    tags = models.ManyToManyField(
        Tag,
        through="FeedbackTag",
        related_name="feedbacks",
        blank=True,
    )

    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feedbacks"
        ordering = ["-submitted_at", "-id"]
        indexes = [
            models.Index(fields=["product", "status"]),
            models.Index(fields=["source", "submitted_at"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["author", "submitted_at"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"FB-{self.id:04d}"
            Feedback.objects.filter(pk=self.pk).update(code=self.code)

    def __str__(self) -> str:
        return f"{self.code or self.id} - {self.title}"


class FeedbackTag(models.Model):
    feedback = models.ForeignKey(
        Feedback,
        on_delete=models.CASCADE,
        related_name="feedback_tag_links",
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name="tag_feedback_links",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_feedback_tags",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedback_tags"
        constraints = [
            models.UniqueConstraint(
                fields=["feedback", "tag"],
                name="unique_feedback_tag",
            )
        ]
