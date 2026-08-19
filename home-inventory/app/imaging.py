"""Thumbnail generation for phone photos."""

import io

import pillow_heif
from PIL import Image, ImageOps

# Pillow still has no native HEIF decoding. iOS Safari transcodes to JPEG for accept="image/*",
# so this is a safety net for share-sheet and Android paths rather than the common case.
pillow_heif.register_heif_opener()

THUMB_LONG_EDGE = 512
THUMB_CONTENT_TYPE = "image/webp"

# A 48MP phone photo decodes to ~145MB of RGB. Pillow's default bomb guard is well above that,
# so raise it deliberately rather than having it trip on a legitimate photo.
Image.MAX_IMAGE_PIXELS = 80_000_000


class UnreadableImage(Exception):
    pass


def make_thumbnail(data: bytes, long_edge: int = THUMB_LONG_EDGE) -> bytes:
    """Return a WebP thumbnail, correctly rotated, for browsing views."""
    try:
        image = Image.open(io.BytesIO(data))
        # Decode JPEGs at a reduced scale where possible; on a 48MP photo this is the difference
        # between ~145MB of RGB and a few MB.
        image.draft("RGB", (long_edge * 2, long_edge * 2))
        image = ImageOps.exif_transpose(image)
    except Exception as exc:
        raise UnreadableImage(str(exc)) from exc

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail((long_edge, long_edge))

    out = io.BytesIO()
    image.save(out, "WEBP", quality=80, method=4)
    return out.getvalue()


def extension_for(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/heic": "heic",
        "image/heif": "heif",
        "image/gif": "gif",
    }.get(content_type, "bin")
