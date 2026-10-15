import uuid

from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction, AuditResult, DocumentAuditLog
from apps.audit.services import record_document_audit

from .filters import DocumentFilter
from .models import DocumentStatus
from .permissions import DocumentPermission
from .selectors import document_queryset_for_user
from .serializers import (
    DocumentCreateSerializer,
    DocumentReadSerializer,
    DocumentUpdateSerializer,
    DownloadResponseSerializer,
    WebSocketTicketSerializer,
)
from .services import create_document, delete_document, update_document
from .storage import get_storage
from .tickets import issue_ticket


@extend_schema_view(
    create=extend_schema(
        request=DocumentCreateSerializer, responses={202: DocumentReadSerializer}
    ),
    update=extend_schema(
        request=DocumentUpdateSerializer,
        responses={200: DocumentReadSerializer, 202: DocumentReadSerializer},
    ),
    partial_update=extend_schema(
        request=DocumentUpdateSerializer,
        responses={200: DocumentReadSerializer, 202: DocumentReadSerializer},
    ),
)
class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DocumentPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DocumentFilter
    search_fields = ["title", "original_filename"]
    ordering_fields = ["created_at", "updated_at", "title", "size_bytes"]
    ordering = ["-created_at", "-id"]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return document_queryset_for_user(self.request.user)

    def permission_denied(self, request, message=None, code=None):
        raw_id = self.kwargs.get("pk")
        if raw_id and request.user.is_authenticated:
            try:
                document_id = uuid.UUID(str(raw_id))
            except ValueError:
                document_id = None
            if document_id:
                target = (
                    self.get_queryset()
                    .model.objects.filter(pk=document_id)
                    .only("id", "title")
                    .first()
                )
                DocumentAuditLog.objects.create(
                    actor=request.user,
                    actor_id_snapshot=str(request.user.pk),
                    actor_username_snapshot=request.user.get_username(),
                    document=target,
                    document_id_snapshot=document_id,
                    document_title_snapshot=target.title if target else "",
                    action=AuditAction.ACCESS_DENIED,
                    result=AuditResult.DENIED,
                )
        return super().permission_denied(request, message=message, code=code)

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentCreateSerializer
        if self.action in ("update", "partial_update"):
            return DocumentUpdateSerializer
        if self.action == "download":
            return DownloadResponseSerializer
        return DocumentReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = create_document(
            owner=request.user,
            title=serializer.validated_data["title"],
            upload=serializer.validated_data["file"],
            file_metadata=serializer.file_metadata,
            request=request,
        )
        return Response(
            DocumentReadSerializer(document).data, status=status.HTTP_202_ACCEPTED
        )

    def retrieve(self, request, *args, **kwargs):
        document = self.get_object()
        record_document_audit(
            document=document,
            actor=request.user,
            request=request,
            action=AuditAction.RETRIEVE,
        )
        return Response(DocumentReadSerializer(document).data)

    def _update(self, request, partial):
        document = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data.get("file")
        try:
            updated = update_document(
                document=document,
                actor=request.user,
                title=serializer.validated_data.get("title"),
                upload=upload,
                file_metadata=getattr(serializer, "file_metadata", None),
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            DocumentReadSerializer(updated).data,
            status=status.HTTP_202_ACCEPTED if upload else status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        delete_document(document=document, actor=request.user, request=request)
        return Response(status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses=DownloadResponseSerializer)
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        if document.status != DocumentStatus.READY or not document.object_key:
            return Response(
                {"detail": "Document is not ready for download."},
                status=status.HTTP_409_CONFLICT,
            )
        url = get_storage().presigned_download(
            document.object_key,
            document.original_filename,
            settings.DOCUMENT_PRESIGNED_URL_TTL,
        )
        record_document_audit(
            document=document,
            actor=request.user,
            request=request,
            action=AuditAction.DOWNLOAD_LINK_ISSUED,
        )
        return Response({"url": url, "expires_in": settings.DOCUMENT_PRESIGNED_URL_TTL})


class WebSocketTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: WebSocketTicketSerializer})
    def post(self, request):
        return Response(
            {
                "ticket": issue_ticket(request.user),
                "expires_in": settings.WEBSOCKET_TICKET_TTL,
            }
        )
