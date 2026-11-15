from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.evaluation import validate_upload


def test_validate_image_and_text() -> None:
    image_bytes = BytesIO()
    Image.new("RGB", (20, 10), "green").save(image_bytes, format="PNG")
    image = validate_upload(image_bytes.getvalue(), "image", "application/octet-stream")
    assert image.media_type == "image/png"
    assert image.size_bytes > 0

    text = validate_upload(b"a useful text sample", "text", "text/plain")
    assert text.media_type == "text/plain"
    assert len(text.sha256) == 64


@pytest.mark.parametrize("content", [b"", b" \n\t", b"\xff"])
def test_invalid_text_is_rejected(content: bytes) -> None:
    with pytest.raises(ValueError):
        validate_upload(content, "text", "text/plain")
