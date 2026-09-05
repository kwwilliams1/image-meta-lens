"""PNG parsing: dimensions and color info from IHDR, key/value pairs from
tEXt/zTXt/iTXt chunks.
"""

import os
import struct
import zlib

from .errors import UnsupportedFormatError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

COLOR_TYPES = {
    0: "grayscale",
    2: "truecolor",
    3: "indexed",
    4: "grayscale+alpha",
    6: "truecolor+alpha",
}


def parse_png(path):
    with open(path, "rb") as f:
        if f.read(8) != PNG_SIGNATURE:
            raise UnsupportedFormatError(f"not a PNG file: {path}")

        image = {}
        text = {}
        while True:
            header = f.read(8)
            if len(header) < 8:
                break
            length, chunk_type = struct.unpack(">I4s", header)
            data = f.read(length)
            f.read(4)  # CRC, not verified

            if chunk_type == b"IHDR" and len(data) >= 10:
                width, height, bit_depth, color_type = struct.unpack(">IIBB", data[:10])
                image["width"] = width
                image["height"] = height
                image["bit_depth"] = bit_depth
                image["color_type"] = COLOR_TYPES.get(color_type, color_type)
            elif chunk_type == b"tEXt" and b"\x00" in data:
                keyword, _, value = data.partition(b"\x00")
                text[keyword.decode("latin-1")] = value.decode("latin-1")
            elif chunk_type == b"zTXt":
                entry = _parse_ztxt(data)
                if entry is not None:
                    text[entry[0]] = entry[1]
            elif chunk_type == b"iTXt":
                entry = _parse_itxt(data)
                if entry is not None:
                    text[entry[0]] = entry[1]
            elif chunk_type == b"IEND":
                break

    return {
        "path": path,
        "format": "PNG",
        "file_size": os.path.getsize(path),
        "image": image,
        "text": text,
    }


def _parse_ztxt(data):
    """zTXt: keyword\\0 compression_method(1) zlib-compressed latin-1 text."""
    keyword, sep, rest = data.partition(b"\x00")
    if not sep or len(rest) < 1:
        return None
    # rest[0] is the compression method; 0 (deflate) is the only one defined.
    try:
        value = zlib.decompress(rest[1:]).decode("latin-1")
    except zlib.error:
        return None
    return keyword.decode("latin-1"), value


def _parse_itxt(data):
    """iTXt: keyword\\0 compressed(1) method(1) language\\0 translated\\0 text.

    The text is UTF-8, optionally zlib-compressed; keyword stays Latin-1 per
    spec even though the rest of the chunk is UTF-8.
    """
    keyword, sep, rest = data.partition(b"\x00")
    if not sep or len(rest) < 2:
        return None
    compressed = rest[0]
    rest = rest[2:]  # skip compressed flag and compression method
    _language, sep, rest = rest.partition(b"\x00")
    if not sep:
        return None
    _translated_keyword, sep, rest = rest.partition(b"\x00")
    if not sep:
        return None
    if compressed:
        try:
            rest = zlib.decompress(rest)
        except zlib.error:
            return None
    try:
        value = rest.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return keyword.decode("latin-1"), value
