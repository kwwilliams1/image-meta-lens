"""PNG parsing: dimensions and color info from IHDR, key/value pairs from
tEXt chunks. iTXt/zTXt (compressed or international text) aren't handled
yet -- see README roadmap.
"""

import os
import struct

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
            elif chunk_type == b"IEND":
                break

    return {
        "path": path,
        "format": "PNG",
        "file_size": os.path.getsize(path),
        "image": image,
        "text": text,
    }
