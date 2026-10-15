import hashlib
import io
import zipfile
from pathlib import Path, PurePath

import magic
from django.conf import settings
from rest_framework import serializers

ALLOWED = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".txt": {"text/plain"},
    ".csv": {"text/plain", "text/csv", "application/csv"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    },
}
OFFICE_MARKERS = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}


def safe_filename(name: str) -> str:
    clean = PurePath(name.replace("\\", "/")).name.replace("\x00", "").strip()
    return clean[:255] or "document"


def _office_mime(data: bytes, extension: str) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if len(names) > 10_000 or not any(
                n.startswith(OFFICE_MARKERS[extension]) for n in names
            ):
                return None
    except (zipfile.BadZipFile, KeyError):
        return None
    return next(iter(ALLOWED[extension]))


def validate_document_file(upload):
    if upload.size > settings.DOCUMENT_MAX_UPLOAD_SIZE:
        raise serializers.ValidationError(
            f"File exceeds the {settings.DOCUMENT_MAX_UPLOAD_SIZE} byte limit."
        )
    extension = Path(upload.name).suffix.lower()
    if extension not in ALLOWED:
        raise serializers.ValidationError("Unsupported document extension.")
    data = upload.read()
    upload.seek(0)
    detected = magic.from_buffer(data[:8192], mime=True)
    if extension in OFFICE_MARKERS:
        detected = _office_mime(data, extension)
    if detected not in ALLOWED[extension]:
        raise serializers.ValidationError("File content does not match its extension.")
    return {
        "original_filename": safe_filename(upload.name),
        "content_type": detected,
        "size_bytes": upload.size,
        "checksum_sha256": hashlib.sha256(data).hexdigest(),
    }
