"""WebP parsing: dimensions from the VP8/VP8L/VP8X bitstream chunks, plus
Exif and GPS fields when an EXIF chunk is present. WebP is a RIFF container,
so this is chunk-walking rather than bitstream decoding -- the only chunk
payload bytes actually interpreted are the handful that carry dimensions.
"""

import os
import struct

from .errors import UnsupportedFormatError
from .jpeg import _parse_exif

_RIFF = b"RIFF"
_WEBP = b"WEBP"

# VP8X flags byte: bit 5 = ICC profile, bit 4 = alpha, bit 3 = Exif,
# bit 2 = XMP, bit 1 = animation. Bits 0, 6, 7 are reserved.
_VP8X_FLAG_ALPHA = 0x10
_VP8X_FLAG_ANIMATION = 0x02


def parse_webp(path):
    with open(path, "rb") as f:
        header = f.read(12)
        if len(header) < 12 or header[:4] != _RIFF or header[8:12] != _WEBP:
            raise UnsupportedFormatError(f"not a WebP file: {path}")

        image = {}
        exif = {}
        gps = {}
        for fourcc, data in _iter_chunks(f):
            if fourcc == b"VP8X" and len(data) >= 10:
                flags = data[0]
                image["width"] = int.from_bytes(data[4:7], "little") + 1
                image["height"] = int.from_bytes(data[7:10], "little") + 1
                image["has_alpha"] = bool(flags & _VP8X_FLAG_ALPHA)
                image["has_animation"] = bool(flags & _VP8X_FLAG_ANIMATION)
            elif fourcc == b"VP8 " and "width" not in image:
                dims = _parse_vp8_dims(data)
                if dims is not None:
                    image["width"], image["height"] = dims
            elif fourcc == b"VP8L" and "width" not in image:
                dims = _parse_vp8l_dims(data)
                if dims is not None:
                    image["width"], image["height"] = dims
            elif fourcc == b"EXIF":
                # Chunk contents are raw TIFF; some encoders (wrongly)
                # prefix it with the "Exif\0\0" marker used in JPEG APP1.
                tiff = data[6:] if data[:6] == b"Exif\x00\x00" else data
                tags, gps_tags = _parse_exif(tiff)
                exif.update(tags)
                gps.update(gps_tags)

    result = {
        "path": path,
        "format": "WEBP",
        "file_size": os.path.getsize(path),
        "image": image,
        "exif": exif,
    }
    if gps:
        result["gps"] = gps
    return result


def _iter_chunks(f):
    while True:
        chunk_header = f.read(8)
        if len(chunk_header) < 8:
            return
        fourcc, size = struct.unpack("<4sI", chunk_header)
        data = f.read(size)
        if len(data) < size:
            return
        if size % 2:
            f.read(1)  # chunks are padded to an even length
        yield fourcc, data


def _parse_vp8_dims(data):
    """VP8 (lossy) frame header: 3-byte frame tag, 3-byte start code
    (0x9d 0x01 0x2a), then 14-bit width and 14-bit height (each paired with
    a 2-bit scale factor we don't need), little-endian.
    """
    if len(data) < 10 or data[3:6] != b"\x9d\x01\x2a":
        return None
    width, height = struct.unpack("<HH", data[6:10])
    return width & 0x3FFF, height & 0x3FFF


def _parse_vp8l_dims(data):
    """VP8L (lossless) header: 1-byte signature (0x2f), then a 4-byte
    little-endian bitfield holding (width - 1) and (height - 1) as 14-bit
    values, followed by an alpha flag and a 3-bit version number.
    """
    if len(data) < 5 or data[0] != 0x2F:
        return None
    bits = int.from_bytes(data[1:5], "little")
    width = (bits & 0x3FFF) + 1
    height = ((bits >> 14) & 0x3FFF) + 1
    return width, height
