import uuid


def staging_key(document_id) -> str:
    return f"staging/{document_id}/{uuid.uuid4()}"


def final_key(document_id, operation_id=None) -> str:
    return f"documents/{document_id}/{operation_id or uuid.uuid4()}"
