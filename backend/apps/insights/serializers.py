from rest_framework import serializers

from apps.accounts.serializers import UserMinimalSerializer
from apps.notifications.models import Vote
from apps.roadmap.models import RoadmapItem
from .models import InsightFeedback, InsightGroup


class InsightMemberSerializer(serializers.ModelSerializer):
    feedback_id = serializers.IntegerField(source="feedback.id", read_only=True)
    code = serializers.CharField(source="feedback.code", read_only=True)
    title = serializers.CharField(source="feedback.title", read_only=True)
    content = serializers.CharField(source="feedback.content", read_only=True)
    sender_name = serializers.CharField(source="feedback.sender_name", read_only=True)
    sender_email = serializers.EmailField(source="feedback.sender_email", read_only=True)
    source_code = serializers.CharField(source="feedback.source.code", read_only=True)
    impact_level = serializers.CharField(source="feedback.impact_level", read_only=True)
    status = serializers.CharField(source="feedback.status", read_only=True)
    created_at = serializers.DateTimeField(source="feedback.created_at", read_only=True)

    class Meta:
        model = InsightFeedback
        fields = [
            "id",
            "feedback_id",
            "code",
            "title",
            "content",
            "sender_name",
            "sender_email",
            "source_code",
            "impact_level",
            "status",
            "similarity_to_centroid",
            "created_at",
        ]


class LinkedRoadmapBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoadmapItem
        fields = ["id", "code", "title", "status", "visibility", "quarter", "progress_percent"]


class InsightGroupListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    assigned_to_detail = UserMinimalSerializer(source="assigned_to", read_only=True)
    affected_customers_count = serializers.IntegerField(read_only=True)
    votes_count = serializers.SerializerMethodField()
    user_has_voted = serializers.SerializerMethodField()

    class Meta:
        model = InsightGroup
        fields = [
            "id",
            "code",
            "product",
            "product_name",
            "title",
            "description",
            "priority_score",
            "priority_level",
            "volume_score",
            "impact_score",
            "severity_score",
            "status",
            "verification_status",
            "feedback_count",
            "affected_customers_count",
            "assigned_to",
            "assigned_to_detail",
            "votes_count",
            "user_has_voted",
            "created_at",
        ]

    def get_votes_count(self, obj: InsightGroup) -> int:
        return obj.votes.count()

    def get_user_has_voted(self, obj: InsightGroup) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return Vote.objects.filter(user=user, insight_group=obj).exists()


class InsightGroupDetailSerializer(InsightGroupListSerializer):
    members = InsightMemberSerializer(source="insight_feedback_links", many=True, read_only=True)
    roadmap_items = LinkedRoadmapBriefSerializer(many=True, read_only=True)
    priority_reasoning = serializers.CharField(read_only=True)

    class Meta(InsightGroupListSerializer.Meta):
        fields = InsightGroupListSerializer.Meta.fields + [
            "possible_causes",
            "ai_recommendations",
            "draft_customer_reply",
            "priority_reasoning",
            "members",
            "roadmap_items",
        ]


class InsightGroupWriteSerializer(serializers.ModelSerializer):
    feedback_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = InsightGroup
        fields = [
            "id",
            "product",
            "title",
            "description",
            "possible_causes",
            "ai_recommendations",
            "draft_customer_reply",
            "priority_score",
            "priority_level",
            "status",
            "verification_status",
            "assigned_to",
            "feedback_ids",
        ]


class RunAIPipelineSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False, allow_null=True)
    similarity_threshold = serializers.FloatField(default=0.72, min_value=0.40, max_value=0.98)
    eps = serializers.FloatField(default=0.48, min_value=0.05, max_value=0.95)
    min_samples = serializers.IntegerField(default=2, min_value=2, max_value=15)
    use_llm = serializers.BooleanField(default=True)
    include_clustered = serializers.BooleanField(default=False)
