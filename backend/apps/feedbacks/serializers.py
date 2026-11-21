from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.models import Role
from apps.accounts.serializers import UserMinimalSerializer
from apps.insights.models import InsightGroup
from apps.notifications.models import Vote
from .models import Feedback, FeedbackReply, FeedbackSource, FeedbackTag, Product, Tag


class ProductSerializer(serializers.ModelSerializer):
    feedback_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "feedback_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_slug(self, value: str) -> str:
        return slugify(value)


class FeedbackSourceSerializer(serializers.ModelSerializer):
    feedback_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = FeedbackSource
        fields = [
            "id",
            "code",
            "name",
            "is_active",
            "feedback_count",
        ]
        read_only_fields = ["id", "code"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "color"]
        read_only_fields = ["id"]

    def validate_slug(self, value: str) -> str:
        return slugify(value)


class RelatedInsightBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightGroup
        fields = ["id", "code", "title", "priority_score", "priority_level", "status"]


class DuplicateSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "code", "title", "status"]


class FeedbackListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    source_code = serializers.CharField(source="source.code", read_only=True)
    source_name = serializers.CharField(source="source.name", read_only=True)
    assigned_to_detail = UserMinimalSerializer(source="assigned_to", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    related_insights = RelatedInsightBriefSerializer(source="insight_groups", many=True, read_only=True)
    votes_count = serializers.SerializerMethodField()
    user_has_voted = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = [
            "id",
            "code",
            "title",
            "content",
            "ai_summary",
            "sender_name",
            "sender_email",
            "author",
            "product",
            "product_name",
            "source",
            "source_code",
            "source_name",
            "status",
            "impact_level",
            "priority_score",
            "assigned_to",
            "assigned_to_detail",
            "duplicate_of",
            "similarity_score",
            "is_duplicate_confirmed",
            "tags",
            "related_insights",
            "votes_count",
            "user_has_voted",
            "created_at",
            "updated_at",
        ]

    def get_votes_count(self, obj: Feedback) -> int:
        if hasattr(obj, "annotated_votes_count"):
            return obj.annotated_votes_count
        return obj.votes.count()

    def get_user_has_voted(self, obj: Feedback) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if hasattr(obj, "prefetched_user_voted"):
            return obj.prefetched_user_voted
        return Vote.objects.filter(user=user, feedback=obj).exists()


class FeedbackReplySerializer(serializers.ModelSerializer):
    author_detail = UserMinimalSerializer(source="author", read_only=True)

    class Meta:
        model = FeedbackReply
        fields = [
            "id",
            "feedback",
            "author",
            "author_detail",
            "is_staff_reply",
            "message",
            "created_at",
        ]
        read_only_fields = ["id", "feedback", "author", "is_staff_reply", "created_at"]


class FeedbackDetailSerializer(FeedbackListSerializer):
    duplicate_of_detail = DuplicateSummarySerializer(source="duplicate_of", read_only=True)
    author_detail = UserMinimalSerializer(source="author", read_only=True)
    replies = FeedbackReplySerializer(many=True, read_only=True)

    class Meta(FeedbackListSerializer.Meta):
        fields = FeedbackListSerializer.Meta.fields + [
            "duplicate_of_detail",
            "author_detail",
            "replies",
        ]


class FeedbackWriteSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )
    source_code = serializers.ChoiceField(
        choices=FeedbackSource.SOURCE_CHOICES,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Feedback
        fields = [
            "id",
            "title",
            "content",
            "ai_summary",
            "sender_name",
            "sender_email",
            "product",
            "source",
            "source_code",
            "status",
            "impact_level",
            "priority_score",
            "assigned_to",
            "tag_ids",
        ]
        extra_kwargs = {
            "source": {"required": False},
            "sender_name": {"required": False},
            "sender_email": {"required": False},
            "ai_summary": {"required": False},
        }

    def validate(self, attrs):
        if not attrs.get("source") and attrs.get("source_code"):
            source = FeedbackSource.objects.filter(code=attrs["source_code"]).first()
            if not source:
                raise serializers.ValidationError({"source_code": "Nguồn tiếp nhận không tồn tại."})
            attrs["source"] = source
        return attrs

    def create(self, validated_data):
        tag_ids = validated_data.pop("tag_ids", [])
        validated_data.pop("source_code", None)
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not validated_data.get("source"):
            web_source, _ = FeedbackSource.objects.get_or_create(
                code=FeedbackSource.WEB_FORM,
                defaults={"name": "Website Form"},
            )
            validated_data["source"] = web_source

        if user and user.is_authenticated:
            if user.role_code == Role.CUSTOMER:
                validated_data["author"] = user
                validated_data["sender_name"] = user.display_name()
                validated_data["sender_email"] = user.email
                validated_data["status"] = Feedback.STATUS_NEW
                validated_data.pop("assigned_to", None)
                validated_data.pop("priority_score", None)
            else:
                validated_data.setdefault("author", user)
                if not (validated_data.get("sender_name") or "").strip():
                    validated_data["sender_name"] = user.display_name()
                if not (validated_data.get("sender_email") or "").strip():
                    validated_data["sender_email"] = user.email

        feedback = Feedback.objects.create(**validated_data)
        if tag_ids:
            for tag in Tag.objects.filter(id__in=tag_ids):
                FeedbackTag.objects.get_or_create(feedback=feedback, tag=tag)
        return feedback

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop("tag_ids", None)
        validated_data.pop("source_code", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tag_ids is not None:
            FeedbackTag.objects.filter(feedback=instance).exclude(tag_id__in=tag_ids).delete()
            for tag in Tag.objects.filter(id__in=tag_ids):
                FeedbackTag.objects.get_or_create(feedback=instance, tag=tag)
        return instance


class MultiSourceIngestSerializer(serializers.Serializer):
    source_code = serializers.ChoiceField(choices=FeedbackSource.SOURCE_CHOICES)
    product_id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    sender_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    sender_email = serializers.EmailField(required=False, allow_blank=True)
    impact_level = serializers.ChoiceField(
        choices=Feedback.IMPACT_CHOICES,
        default=Feedback.IMPACT_MEDIUM,
    )
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
