from .models import AuditResult, DocumentAuditLog


def client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (
        forwarded.split(",", 1)[0].strip()
        if forwarded
        else request.META.get("REMOTE_ADDR")
    )


def record_document_audit(
    *,
    document,
    action: str,
    actor=None,
    request=None,
    result=AuditResult.SUCCESS,
    metadata=None,
):
    return DocumentAuditLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        actor_id_snapshot=str(actor.pk) if actor and actor.is_authenticated else "",
        actor_username_snapshot=actor.get_username()
        if actor and actor.is_authenticated
        else "",
        document=document,
        document_id_snapshot=document.pk,
        document_title_snapshot=document.title,
        action=action,
        result=result,
        ip_address=client_ip(request),
        request_id=request.headers.get("X-Request-ID", "")[:64] if request else "",
        metadata=metadata or {},
    )
