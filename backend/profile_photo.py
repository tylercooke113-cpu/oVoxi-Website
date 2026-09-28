"""Profile photo processing. See docs/PRD-03 section 11, decision 19.

Pure: bytes in, WebP bytes out. No R2, no DB. Called in a worker thread.
Every output is re-encoded from pixels only, so no metadata (EXIF, GPS,
camera details, embedded thumbnails, comments) survives.
"""
from io import BytesIO

from PIL import Image, ImageOps

PHOTO_CONTENT_TYPES = ("image/jpeg", "image/png", "image/webp")
ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000           # ~40 megapixels: guards against decompression bombs
PHOTO_SIZES = (800, 200)
WEBP_QUALITY = 85
BACKGROUND = (0, 0, 0)            # transparent areas become the site's black
WORKING_EDGE = 1600                # longest side kept while cropping (2x the largest output)

REJECT_MESSAGE = "That image couldn't be read. Use a JPEG, PNG or WebP under 10 MB."


class PhotoRejected(ValueError):
    pass


def process_photo(data: bytes) -> dict:
    """Return {800: webp_bytes, 200: webp_bytes}. Raises PhotoRejected."""
    if not data or len(data) > MAX_PHOTO_BYTES:
        raise PhotoRejected(REJECT_MESSAGE)
    try:
        probe = Image.open(BytesIO(data))      # lazy: reads the header only
        fmt, (w, h) = probe.format, probe.size
    except Exception as exc:
        raise PhotoRejected(REJECT_MESSAGE) from exc
    if fmt not in ALLOWED_FORMATS or w * h > MAX_PIXELS or w < 1 or h < 1:
        raise PhotoRejected(REJECT_MESSAGE)

    try:
        img = Image.open(BytesIO(data))
        if fmt == "JPEG":
            # Let the JPEG decoder skip detail we would throw away: it decodes at
            # 1/2, 1/4 or 1/8 scale while keeping both sides >= the largest output.
            img.draft("RGB", (PHOTO_SIZES[0], PHOTO_SIZES[0]))
        img.load()
        img = ImageOps.exif_transpose(img)     # apply camera rotation, then drop the tag
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            flat = Image.new("RGB", rgba.size, BACKGROUND)
            flat.paste(rgba, mask=rgba.split()[3])
            img = flat
        else:
            img = img.convert("RGB")
        # Shrink early so the steps below work on at most WORKING_EDGE pixels a side.
        img.thumbnail((WORKING_EDGE, WORKING_EDGE), Image.LANCZOS, reducing_gap=2.0)
        # Fresh image from the raw pixel bytes only: nothing from the original's
        # info (EXIF, XMP, ICC, comments) survives. One C-level copy, not a
        # per-pixel Python list (which used ~1 GB for a 12 MP photo).
        clean = Image.frombytes("RGB", img.size, img.tobytes())
        out = {}
        for size in PHOTO_SIZES:
            square = ImageOps.fit(clean, (size, size), Image.LANCZOS, centering=(0.5, 0.5))
            buf = BytesIO()
            square.save(buf, "WEBP", quality=WEBP_QUALITY, method=4)
            out[size] = buf.getvalue()
        return out
    except PhotoRejected:
        raise
    except Exception as exc:
        raise PhotoRejected(REJECT_MESSAGE) from exc
