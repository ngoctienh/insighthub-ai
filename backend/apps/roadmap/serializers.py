from rest_framework import serializers

from apps.accounts.serializers import UserMinimalSerializer
from apps.insights.models import InsightGroup
from .models import RoadmapItem, RoadmapItemInsight


class LinkedInsightSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightGroup
        fields = [
            "id",
            "code",
            "title",
            "priority_score",
            "priority_level",
            "feedback_count",
            "status",
        ]


class PublicRoadmapItemSerializer(serializers.ModelSerializer):
    """Sanitized serializer for public roadmap: strictly excludes internal notes & staff info."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    summary = serializers.SerializerMethodField()
    linked_insights_count = serializers.SerializerMethodField()
    total_linked_feedbacks = serializers.SerializerMethodField()

    class Meta:
        model = RoadmapItem
        fields = [
            "id",
            "code",
            "product",
            "product_name",
            "title",
            "summary",
            "status",
            "quarter",
            "target_start_date",
            "target_end_date",
            "progress_percent",
            "linked_insights_count",
            "total_linked_feedbacks",
            "updated_at",
        ]

    def get_summary(self, obj: RoadmapItem) -> str:
        return obj.public_description.strip() or obj.description

    def get_linked_insights_count(self, obj: RoadmapItem) -> int:
        return obj.insight_groups.count()

    def get_total_linked_feedbacks(self, obj: RoadmapItem) -> int:
        return sum(ins.feedback_count for ins in obj.insight_groups.all())


class RoadmapItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    owner_detail = UserMinimalSerializer(source="owner", read_only=True)
    created_by_detail = UserMinimalSerializer(source="created_by", read_only=True)
    linked_insights = LinkedInsightSummarySerializer(source="insight_groups", many=True, read_only=True)
    insight_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = RoadmapItem
        fields = [
            "id",
            "code",
            "product",
            "product_name",
            "title",
            "description",
            "public_description",
            "internal_notes",
            "status",
            "visibility",
            "quarter",
            "target_start_date",
            "target_end_date",
            "progress_percent",
            "owner",
            "owner_detail",
            "created_by",
            "created_by_detail",
            "linked_insights",
            "insight_group_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_by", "created_at", "updated_at"]

    def validate_progress_percent(self, value: int) -> int:
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tiến độ phải nằm trong khoảng 0 đến 100.")
        return value

    def create(self, validated_data):
        insight_ids = validated_data.pop("insight_group_ids", [])
        request = self.context.get("request")
        user = getattr(request, "user", None)
        item = RoadmapItem.objects.create(
            created_by=user if (user and user.is_authenticated) else None,
            **validated_data,
        )
        for ins in InsightGroup.objects.filter(id__in=insight_ids):
            RoadmapItemInsight.objects.get_or_create(roadmap_item=item, insight_group=ins)
            if item.status == RoadmapItem.STATUS_COMPLETED:
                ins.status = InsightGroup.STATUS_COMPLETED
            elif item.status == RoadmapItem.STATUS_IN_PROGRESS and ins.status in (
                InsightGroup.STATUS_NEW,
                InsightGroup.STATUS_ANALYZING,
                InsightGroup.STATUS_PLANNED,
            ):
                ins.status = InsightGroup.STATUS_IN_PROGRESS
            elif item.status == RoadmapItem.STATUS_PLANNED and ins.status in (
                InsightGroup.STATUS_NEW,
                InsightGroup.STATUS_ANALYZING,
            ):
                ins.status = InsightGroup.STATUS_PLANNED
            ins.save(update_fields=["status", "updated_at"])
        return item

    def update(self, instance, validated_data):
        insight_ids = validated_data.pop("insight_group_ids", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if instance.status == RoadmapItem.STATUS_COMPLETED and instance.progress_percent < 100:
            instance.progress_percent = 100
        instance.save()

        if insight_ids is not None:
            RoadmapItemInsight.objects.filter(roadmap_item=instance).exclude(
                insight_group_id__in=insight_ids
            ).delete()
            for ins in InsightGroup.objects.filter(id__in=insight_ids):
                RoadmapItemInsight.objects.get_or_create(roadmap_item=instance, insight_group=ins)
        return instance
