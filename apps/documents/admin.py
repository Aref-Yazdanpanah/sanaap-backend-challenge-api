from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner", "status", "created_at")
    list_filter = ("status", "content_type")
    search_fields = ("title", "original_filename", "owner__username")
    readonly_fields = (
        "object_key",
        "staging_object_key",
        "checksum_sha256",
        "operation_id",
        "processing_error",
    )
