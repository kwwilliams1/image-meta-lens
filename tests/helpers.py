"""Fixture builders shared by the format test modules.

These build the smallest byte strings that satisfy each parser's format
checks, by hand, rather than shipping binary sample files in the repo.
"""

import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def write(path, data):
    with open(path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------- PNG ----

def _png_chunk(chunk_type, data):
    # The CRC is never checked by the parser, so a dummy value is fine.
    return struct.pack(">I", len(data)) + chunk_type + data + b"\x00\x00\x00\x00"


def build_ihdr(width, height, bit_depth=8, color_type=2):
    return struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)


def build_ztxt(keyword, text):
    return keyword.encode("latin-1") + b"\x00\x00" + zlib.compress(text.encode("latin-1"))


def build_itxt(keyword, text, compressed=False):
    payload = text.encode("utf-8")
    if compressed:
        payload = zlib.compress(payload)
    return (
        keyword.encode("latin-1") + b"\x00"
        + bytes([1 if compressed else 0]) + b"\x00"
        + b"\x00"  # language tag
        + b"\x00"  # translated keyword
        + payload
    )


def build_png(width, height, bit_depth=8, color_type=2, text_chunks=()):
    """text_chunks: list of (chunk_type_bytes, raw_chunk_data) pairs, e.g.
    (b"tEXt", b"Comment\\x00hello") or the output of build_ztxt/build_itxt.
    """
    out = PNG_SIGNATURE
    out += _png_chunk(b"IHDR", build_ihdr(width, height, bit_depth, color_type))
    for chunk_type, data in text_chunks:
        out += _png_chunk(chunk_type, data)
    out += _png_chunk(b"IEND", b"")
    return out


# --------------------------------------------------------------- TIFF ----

def _ifd_size(entries):
    return 2 + 12 * len(entries) + 4


def _extra_len(entries):
    total = 0
    for _tag, _type_id, _count, value in entries:
        if len(value) > 4:
            total += len(value) + (len(value) % 2)
    return total


def _pack_ifd(entries, base_offset, endian):
    extra_start = base_offset + _ifd_size(entries)
    body = struct.pack(endian + "H", len(entries))
    extra = bytearray()
    for tag, type_id, count, value in entries:
        if len(value) <= 4:
            field = value + b"\x00" * (4 - len(value))
        else:
            field = struct.pack(endian + "I", extra_start + len(extra))
            extra += value
            if len(value) % 2:
                extra += b"\x00"
        body += struct.pack(endian + "HHI", tag, type_id, count) + field
    body += struct.pack(endian + "I", 0)  # no next IFD
    return body, bytes(extra)


def build_tiff(endian="<", make=b"TestCam\x00", model=b"X100\x00"):
    """A minimal Exif TIFF blob: IFD0 (Make/Model) pointing at an Exif IFD
    (DateTimeOriginal/FNumber) and a GPS IFD (lat/long as N/40.75, W/73.9833...).
    """
    exif_entries = [
        (0x9003, 2, len(b"2024:06:01 14:22:03\x00"), b"2024:06:01 14:22:03\x00"),
        (0x829D, 5, 1, struct.pack(endian + "II", 28, 10)),  # FNumber f/2.8
    ]
    gps_entries = [
        (0x0001, 2, 2, b"N\x00"),
        (0x0002, 5, 3, b"".join(struct.pack(endian + "II", n, 1) for n in (40, 45, 0))),
        (0x0003, 2, 2, b"W\x00"),
        (0x0004, 5, 3, b"".join(struct.pack(endian + "II", n, 1) for n in (73, 59, 0))),
    ]

    ifd0_offset = 8
    ifd0_entries_count = 4  # Make, Model, ExifIFD pointer, GPSIFD pointer
    ifd0_extra_len = sum(
        len(v) + (len(v) % 2) for v in (make, model) if len(v) > 4
    )
    exif_ifd_offset = ifd0_offset + _ifd_size([None] * ifd0_entries_count) + ifd0_extra_len
    gps_ifd_offset = exif_ifd_offset + _ifd_size(exif_entries) + _extra_len(exif_entries)

    ifd0_entries = [
        (0x010F, 2, len(make), make),
        (0x0110, 2, len(model), model),
        (0x8769, 4, 1, struct.pack(endian + "I", exif_ifd_offset)),
        (0x8825, 4, 1, struct.pack(endian + "I", gps_ifd_offset)),
    ]

    ifd0_body, ifd0_extra = _pack_ifd(ifd0_entries, ifd0_offset, endian)
    exif_body, exif_extra = _pack_ifd(exif_entries, exif_ifd_offset, endian)
    gps_body, gps_extra = _pack_ifd(gps_entries, gps_ifd_offset, endian)

    byte_order = b"II" if endian == "<" else b"MM"
    header = byte_order + struct.pack(endian + "H", 42) + struct.pack(endian + "I", ifd0_offset)
    return header + ifd0_body + ifd0_extra + exif_body + exif_extra + gps_body + gps_extra


# --------------------------------------------------------------- JPEG ----

def _marker_segment(marker, payload):
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def build_jpeg(width, height, tiff=None):
    out = b"\xff\xd8"  # SOI
    sof_payload = bytes([8]) + struct.pack(">HH", height, width)
    out += _marker_segment(0xC0, sof_payload)  # SOF0
    if tiff is not None:
        out += _marker_segment(0xE1, b"Exif\x00\x00" + tiff)  # APP1
    out += b"\xff\xda"  # SOS: parsing stops here, no payload needed
    return out


# --------------------------------------------------------------- WebP ----

def _riff(chunks):
    body = b"WEBP"
    for fourcc, data in chunks:
        body += struct.pack("<4sI", fourcc, len(data)) + data
        if len(data) % 2:
            body += b"\x00"
    return b"RIFF" + struct.pack("<I", len(body)) + body


def build_vp8_chunk(width, height):
    return bytes(3) + b"\x9d\x01\x2a" + struct.pack("<HH", width & 0x3FFF, height & 0x3FFF)


def build_vp8l_chunk(width, height):
    bits = ((width - 1) & 0x3FFF) | (((height - 1) & 0x3FFF) << 14)
    return b"\x2f" + bits.to_bytes(4, "little")


def build_vp8x_chunk(width, height, alpha=False, animation=False):
    flags = (0x10 if alpha else 0) | (0x02 if animation else 0)
    return (
        bytes([flags]) + bytes(3)
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )


def build_webp(chunks):
    return _riff(chunks)
