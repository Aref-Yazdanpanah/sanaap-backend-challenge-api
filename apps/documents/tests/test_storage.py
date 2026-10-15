from unittest.mock import Mock, patch

from apps.documents.storage import DocumentStorage


@patch("apps.documents.storage.boto3.client")
def test_presign_uses_public_client(mock_client, settings):
    internal, public = Mock(), Mock()
    mock_client.side_effect = [internal, public]
    public.generate_presigned_url.return_value = "https://storage/signed"
    storage = DocumentStorage()
    result = storage.presigned_download("private/key", "report.pdf", 60)
    assert result == "https://storage/signed"
    public.generate_presigned_url.assert_called_once()
    internal.generate_presigned_url.assert_not_called()


@patch("apps.documents.storage.boto3.client")
def test_upload_sets_content_type_and_checksum(mock_client, settings):
    internal, public = Mock(), Mock()
    mock_client.side_effect = [internal, public]
    storage = DocumentStorage()
    file_obj = Mock()
    storage.upload("staging/key", file_obj, "application/pdf", "abc")
    internal.upload_fileobj.assert_called_once_with(
        file_obj,
        settings.MINIO_BUCKET_NAME,
        "staging/key",
        ExtraArgs={
            "ContentType": "application/pdf",
            "Metadata": {"checksum-sha256": "abc"},
        },
    )
