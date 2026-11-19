from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def apply_review_watermark(image: Image.Image, contribution_id: int) -> Image.Image:
    base = image.convert("RGBA")
    font_size = max(16, min(36, max(1, min(base.size)) // 10))
    font = ImageFont.load_default(size=font_size)
    label = f"REVIEW ONLY - NOT ACCEPTED - ID {contribution_id}"
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    watermark = ImageDraw.Draw(overlay)
    left, top, right, bottom = watermark.textbbox((0, 0), label, font=font, stroke_width=1)
    text_width = int(right - left)
    text_height = int(bottom - top)
    band_height = text_height + 18
    band_gap = max(150, base.height // 2)
    repeat_width = text_width + 36
    for index, y in enumerate(range(-band_height, base.height + band_gap, band_gap)):
        watermark.rectangle((0, y, base.width, y + band_height), fill=(115, 0, 0, 55))
        start_x = -(repeat_width // 2) if index % 2 else 8
        for x in range(start_x, base.width + repeat_width, repeat_width):
            watermark.text(
                (x, y + 8),
                label,
                font=font,
                fill=(255, 255, 255, 190),
                stroke_width=1,
                stroke_fill=(40, 0, 0, 255),
            )
    diagonal_width = max(7, base.width // 65)
    for x in range(-base.height, base.width + base.height, max(95, base.width // 4)):
        watermark.line(
            (x, 0, x + base.height, base.height),
            fill=(215, 0, 0, 28),
            width=diagonal_width,
        )
    combined = Image.alpha_composite(base, overlay)
    banner_height = max(30, min(54, base.height // 7))
    banner = ImageDraw.Draw(combined)
    banner.rectangle(
        (0, base.height - banner_height, base.width, base.height), fill=(120, 0, 0, 105)
    )
    banner.text(
        (10, base.height - banner_height + 7),
        label,
        font=font,
        fill=(255, 255, 255, 210),
        stroke_width=1,
        stroke_fill=(0, 0, 0, 220),
    )
    return combined.convert("RGB")


def encode_protected_preview(image: Image.Image, contribution_id: int) -> bytes:
    image.thumbnail((480, 480), Image.Resampling.LANCZOS)
    output = BytesIO()
    apply_review_watermark(image, contribution_id).save(
        output, format="JPEG", quality=40, optimize=True, subsampling=2
    )
    return output.getvalue()


def protected_image_preview(path: Path, contribution_id: int) -> bytes:
    with Image.open(path) as source:
        return encode_protected_preview(ImageOps.exif_transpose(source), contribution_id)


def stored_protected_image(upload_dir: Path, stored_filename: str, contribution_id: int) -> Path:
    target = upload_dir / f"review-v4-{Path(stored_filename).stem}-{contribution_id}.jpg"
    if not target.is_file():
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(
            protected_image_preview(upload_dir / stored_filename, contribution_id)
        )
        temporary.replace(target)
    return target
