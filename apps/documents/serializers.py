from rest_framework import serializers

from .models import Document
from .validators import validate_document_file


class DocumentReadSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)
    replacement_pending = serializers.BooleanField(read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "owner",
            "original_filename",
            "content_type",
            "size_bytes",
            "status",
            "replacement_pending",
            "created_at",
            "updated_at",
        )


class RejectOwnerMixin:
    def validate(self, attrs):
        if "owner" in self.initial_data:
            raise serializers.ValidationError(
                {"owner": "Document ownership cannot be supplied or changed."}
            )
        return attrs


class DocumentCreateSerializer(RejectOwnerMixin, serializers.Serializer):
    title = serializers.CharField(max_length=255)
    file = serializers.FileField(write_only=True)

    def validate_file(self, value):
        self.file_metadata = validate_document_file(value)
        return value


class DocumentUpdateSerializer(RejectOwnerMixin, serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    file = serializers.FileField(write_only=True, required=False)

    def validate_file(self, value):
        self.file_metadata = validate_document_file(value)
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs:
            raise serializers.ValidationError(
                "At least one of title or file is required."
            )
        return attrs


class DownloadResponseSerializer(serializers.Serializer):
    url = serializers.URLField()
    expires_in = serializers.IntegerField()


class WebSocketTicketSerializer(serializers.Serializer):
    ticket = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)
