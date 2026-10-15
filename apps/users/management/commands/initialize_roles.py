from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from apps.users.roles import ADMIN, EDITOR, VIEWER


class Command(BaseCommand):
    help = "Create or update the three DMS role groups."

    def handle(self, *args, **options):
        admin, _ = Group.objects.get_or_create(name=ADMIN)
        editor, _ = Group.objects.get_or_create(name=EDITOR)
        viewer, _ = Group.objects.get_or_create(name=VIEWER)
        document_permissions = Permission.objects.filter(
            content_type__app_label="documents"
        )
        admin.permissions.set(document_permissions)
        editor.permissions.set(
            document_permissions.filter(
                codename__in=["add_document", "change_document", "view_document"]
            )
        )
        viewer.permissions.set(document_permissions.filter(codename="view_document"))
        self.stdout.write(self.style.SUCCESS("DMS roles initialized."))
