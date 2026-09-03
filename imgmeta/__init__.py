"""Read basic metadata out of image files without any third-party deps.

    >>> import imgmeta
    >>> data = imgmeta.read_metadata("photo.jpg")
    >>> print(imgmeta.format_human(data))
"""

import json

from .errors import UnsupportedFormatError
from .jpeg import parse_jpeg
from .png import PNG_SIGNATURE, parse_png

__all__ = [
    "read_metadata",
    "format_human",
    "format_json",
    "UnsupportedFormatError",
]

__version__ = "0.1.0"


def read_metadata(path):
    """Sniff the file's magic bytes and dispatch to the right parser.

    Returns a plain dict, JSON-serializable as-is except for values inside
    "exif" that come from RATIONAL fields, which are plain floats already.
    """
    with open(path, "rb") as f:
        header = f.read(8)

    if header[:2] == b"\xff\xd8":
        return parse_jpeg(path)
    if header == PNG_SIGNATURE:
        return parse_png(path)
    raise UnsupportedFormatError(f"unrecognized image format: {path}")


def format_json(metadata):
    return json.dumps(metadata, indent=2, sort_keys=True)


def format_human(metadata):
    lines = [f"{metadata['path']} ({metadata['format']}, {metadata['file_size']} bytes)"]

    image = metadata.get("image") or {}
    if "width" in image and "height" in image:
        dims = f"  {image['width']}x{image['height']}"
        if "color_type" in image:
            dims += f", {image['color_type']}, {image.get('bit_depth')}-bit"
        lines.append(dims)

    exif = metadata.get("exif")
    if exif:
        lines.append("  exif:")
        for key in sorted(exif):
            lines.append(f"    {key}: {exif[key]}")

    text = metadata.get("text")
    if text:
        lines.append("  text:")
        for key in sorted(text):
            lines.append(f"    {key}: {text[key]}")

    return "\n".join(lines)
