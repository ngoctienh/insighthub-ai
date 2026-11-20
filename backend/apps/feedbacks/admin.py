from django.contrib import admin

from .models import Feedback, FeedbackSource, FeedbackTag, Product, Tag


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")


@admin.register(FeedbackSource)
class FeedbackSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "color")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "source", "status", "impact_level", "assigned_to", "created_at")
    list_filter = ("status", "impact_level", "source", "product")
    search_fields = ("code", "title", "content", "sender_email")


@admin.register(FeedbackTag)
class FeedbackTagAdmin(admin.ModelAdmin):
    list_display = ("feedback", "tag")
