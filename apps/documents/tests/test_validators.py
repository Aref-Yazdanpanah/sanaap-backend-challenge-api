import base64
import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.serializers import ValidationError

from apps.documents.validators import safe_filename, validate_document_file

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)


def test_safe_filename_removes_path():
    assert safe_filename("../../secret.pdf") == "secret.pdf"
    assert safe_filename("..\\secret.pdf") == "secret.pdf"


@pytest.mark.parametrize(("name", "content"), [("ok.pdf", PDF), ("ok.png", PNG)])
def test_valid_common_files(name, content):
    result = validate_document_file(SimpleUploadedFile(name, content))
    assert result["size_bytes"] == len(content)
    assert len(result["checksum_sha256"]) == 64


def test_unsupported_extension_rejected():
    with pytest.raises(ValidationError):
        validate_document_file(SimpleUploadedFile("run.sh", b"#!/bin/sh"))


def test_mime_mismatch_rejected():
    with pytest.raises(ValidationError):
        validate_document_file(SimpleUploadedFile("fake.pdf", PNG))


def test_size_limit_rejected(settings):
    settings.DOCUMENT_MAX_UPLOAD_SIZE = 3
    with pytest.raises(ValidationError):
        validate_document_file(SimpleUploadedFile("large.pdf", PDF))


def test_valid_docx_container():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    result = validate_document_file(
        SimpleUploadedFile("sample.docx", buffer.getvalue())
    )
    assert "wordprocessingml" in result["content_type"]


def test_arbitrary_zip_disguised_as_docx_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("payload.exe", "x")
    with pytest.raises(ValidationError):
        validate_document_file(SimpleUploadedFile("fake.docx", buffer.getvalue()))
