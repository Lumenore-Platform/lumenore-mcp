import base64

import pytest


def test_file_upload_helpers_reject_invalid_base64(monkeypatch):
    monkeypatch.setenv("ALLOWED_EXTENSIONS", "txt")
    from core.file_upload_client import decode_content, sanitize_file_name

    assert sanitize_file_name("../report.txt") == "report.txt"
    assert decode_content(base64.b64encode(b"hello").decode(), "base64") == b"hello"
    with pytest.raises(Exception):
        decode_content("not base64!", "base64")
