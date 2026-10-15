import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class DomainError(Exception):
    def __init__(
        self, detail: str, *, code: str = "domain_error", status_code: int = 400
    ):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


def exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(
            {"detail": exc.detail, "code": exc.code}, status=exc.status_code
        )
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
    return response
