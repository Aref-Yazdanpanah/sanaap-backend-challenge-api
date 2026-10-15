from django.contrib import admin

from .models import DocumentAuditLog


@admin.register(DocumentAuditLog)
class DocumentAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "action",
        "result",
        "actor_username_snapshot",
        "document_id_snapshot",
    )
    readonly_fields = [field.name for field in DocumentAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
