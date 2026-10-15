from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, WebSocketTicketView

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("ws-ticket/", WebSocketTicketView.as_view(), name="ws-ticket"),
    *router.urls,
]
