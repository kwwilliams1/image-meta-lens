"""JPEG parsing: image dimensions from SOF markers, camera info and GPS
coordinates from the Exif APP1 segment. Only the TIFF tags that show up in
practice for basic metadata reporting are decoded; anything else in the
IFDs is skipped.
"""

import os
import struct

from .errors import UnsupportedFormatError

# JPEG markers that carry no payload and are just skipped over.
_NO_PAYLOAD_MARKERS = {0x01, 0xD8, 0xD9}
_RST_MARKERS = set(range(0xD0, 0xD8))

# Start-of-frame markers that encode width/height. 0xC4, 0xC8 and 0xCC are
# excluded because they're DHT/JPG/DAC, not SOF, despite being in the range.
_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}

_APP1 = 0xE1
_SOS = 0xDA

IFD0_TAGS = {
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x0131: "Software",
    0x0132: "DateTime",
}

EXIF_TAGS = {
    0x829A: "ExposureTime",
    0x829D: "FNumber",
    0x8827: "ISOSpeedRatings",
    0x9003: "DateTimeOriginal",
    0x920A: "FocalLength",
}

GPS_TAGS = {
    0x0001: "GPSLatitudeRef",
    0x0002: "GPSLatitude",
    0x0003: "GPSLongitudeRef",
    0x0004: "GPSLongitude",
    0x0005: "GPSAltitudeRef",
    0x0006: "GPSAltitude",
    0x0007: "GPSTimeStamp",
    0x001D: "GPSDateStamp",
}

_EXIF_IFD_POINTER = 0x8769
_GPS_IFD_POINTER = 0x8825
_IFD_POINTERS = {_EXIF_IFD_POINTER: "exif", _GPS_IFD_POINTER: "gps"}

# byte-length of one value of each TIFF field type, indexed by type id.
_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

# struct format char for the scalar (non-rational) types.
_TYPE_FORMATS = {1: "B", 3: "H", 4: "I", 6: "b", 7: "B", 8: "h", 9: "i", 11: "f", 12: "d"}


def parse_jpeg(path):
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise UnsupportedFormatError(f"not a JPEG file: {path}")

        image = {}
        exif = {}
        gps = {}
        for marker, payload in _iter_segments(f):
            if marker in _SOF_MARKERS and "width" not in image:
                # payload: precision(1) height(2) width(2) ...
                if len(payload) >= 5:
                    height, width = struct.unpack(">HH", payload[1:5])
                    image["width"] = width
                    image["height"] = height
            elif marker == _APP1 and payload.startswith(b"Exif\x00\x00"):
                tags, gps_tags = _parse_exif(payload[6:])
                exif.update(tags)
                gps.update(gps_tags)

    result = {
        "path": path,
        "format": "JPEG",
        "file_size": os.path.getsize(path),
        "image": image,
        "exif": exif,
    }
    if gps:
        result["gps"] = gps
    return result


def _iter_segments(f):
    while True:
        marker_bytes = f.read(2)
        if len(marker_bytes) < 2 or marker_bytes[0] != 0xFF:
            return
        marker = marker_bytes[1]
        if marker in _NO_PAYLOAD_MARKERS or marker in _RST_MARKERS:
            continue
        if marker == _SOS:
            # Compressed scan data follows; nothing after this is a marker
            # segment we care about, so stop scanning.
            return
        length_bytes = f.read(2)
        if len(length_bytes) < 2:
            return
        length = struct.unpack(">H", length_bytes)[0]
        payload = f.read(length - 2)
        if len(payload) < length - 2:
            return
        yield marker, payload


def _parse_exif(tiff):
    if len(tiff) < 8:
        return {}, {}
    byte_order = tiff[:2]
    if byte_order == b"II":
        endian = "<"
    elif byte_order == b"MM":
        endian = ">"
    else:
        return {}, {}

    tags = {}
    gps = {}
    try:
        ifd0_offset = struct.unpack(endian + "I", tiff[4:8])[0]
        sub_ifds = _parse_ifd(tiff, ifd0_offset, endian, IFD0_TAGS, tags)
        exif_offset = sub_ifds.get("exif")
        gps_offset = sub_ifds.get("gps")
        if exif_offset is not None:
            _parse_ifd(tiff, exif_offset, endian, EXIF_TAGS, tags)
        if gps_offset is not None:
            _parse_ifd(tiff, gps_offset, endian, GPS_TAGS, gps)
            _add_decimal_coordinates(gps)
    except (struct.error, IndexError):
        # Truncated or malformed IFD: keep whatever we already decoded.
        pass
    return tags, gps


def _parse_ifd(tiff, offset, endian, tag_names, out):
    """Decode one IFD, writing recognized tags into `out`. Returns a dict of
    any sub-IFD pointers this IFD contained, keyed by name (e.g. "exif",
    "gps").
    """
    count = struct.unpack(endian + "H", tiff[offset:offset + 2])[0]
    entry_offset = offset + 2
    sub_ifds = {}
    for _ in range(count):
        entry = tiff[entry_offset:entry_offset + 12]
        tag, field_type, field_count = struct.unpack(endian + "HHI", entry[:8])
        value = _decode_value(tiff, endian, field_type, field_count, entry[8:12])
        pointer_name = _IFD_POINTERS.get(tag)
        if pointer_name is not None and isinstance(value, int):
            sub_ifds[pointer_name] = value
        elif tag in tag_names and value is not None:
            out[tag_names[tag]] = value
        entry_offset += 12
    return sub_ifds


def _add_decimal_coordinates(gps):
    """Add signed decimal-degree Latitude/Longitude fields derived from the
    raw GPSLatitude/GPSLongitude (degrees, minutes, seconds) tuples, which
    are otherwise awkward for callers to use directly.
    """
    lat = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
    if lat is not None:
        gps["Latitude"] = lat
    lon = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
    if lon is not None:
        gps["Longitude"] = lon


def _dms_to_decimal(dms, ref):
    if not isinstance(dms, tuple) or len(dms) != 3:
        return None
    degrees, minutes, seconds = dms
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def _decode_value(tiff, endian, field_type, count, inline_bytes):
    size_per = _TYPE_SIZES.get(field_type)
    if size_per is None or count <= 0:
        return None
    total = size_per * count
    if total <= 4:
        raw = inline_bytes[:total]
    else:
        offset = struct.unpack(endian + "I", inline_bytes)[0]
        raw = tiff[offset:offset + total]
        if len(raw) < total:
            return None

    if field_type == 2:  # ASCII
        return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")

    if field_type in (5, 10):  # RATIONAL / SRATIONAL
        num_fmt = "I" if field_type == 5 else "i"
        values = []
        for i in range(count):
            num, den = struct.unpack(endian + num_fmt * 2, raw[i * 8:i * 8 + 8])
            values.append(num / den if den else 0.0)
        return values[0] if count == 1 else tuple(values)

    fmt_char = _TYPE_FORMATS.get(field_type)
    if fmt_char is None:
        return None
    values = struct.unpack(endian + fmt_char * count, raw[:size_per * count])
    return values[0] if count == 1 else values
