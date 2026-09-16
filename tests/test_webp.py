import os
import tempfile
import unittest

from imgmeta.errors import UnsupportedFormatError
from imgmeta.webp import parse_webp

from . import helpers


class WebpTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".webp")
        os.close(fd)
        self.addCleanup(os.unlink, self.path)

    def test_vp8_lossy_dimensions(self):
        chunks = [(b"VP8 ", helpers.build_vp8_chunk(320, 240))]
        helpers.write(self.path, helpers.build_webp(chunks))
        data = parse_webp(self.path)

        self.assertEqual(data["format"], "WEBP")
        self.assertEqual(data["image"]["width"], 320)
        self.assertEqual(data["image"]["height"], 240)

    def test_vp8l_lossless_dimensions(self):
        chunks = [(b"VP8L", helpers.build_vp8l_chunk(17, 33))]
        helpers.write(self.path, helpers.build_webp(chunks))
        data = parse_webp(self.path)
        self.assertEqual(data["image"]["width"], 17)
        self.assertEqual(data["image"]["height"], 33)

    def test_vp8x_dimensions_and_flags(self):
        chunks = [(b"VP8X", helpers.build_vp8x_chunk(100, 50, alpha=True, animation=False))]
        helpers.write(self.path, helpers.build_webp(chunks))
        data = parse_webp(self.path)

        self.assertEqual(data["image"]["width"], 100)
        self.assertEqual(data["image"]["height"], 50)
        self.assertTrue(data["image"]["has_alpha"])
        self.assertFalse(data["image"]["has_animation"])

    def test_exif_chunk_with_gps(self):
        chunks = [
            (b"VP8X", helpers.build_vp8x_chunk(4, 4)),
            (b"EXIF", helpers.build_tiff()),
        ]
        helpers.write(self.path, helpers.build_webp(chunks))
        data = parse_webp(self.path)

        self.assertEqual(data["exif"]["Make"], "TestCam")
        self.assertAlmostEqual(data["gps"]["Latitude"], 40 + 45 / 60)
        self.assertAlmostEqual(data["gps"]["Longitude"], -(73 + 59 / 60))

    def test_exif_chunk_with_jpeg_style_prefix(self):
        chunks = [
            (b"VP8X", helpers.build_vp8x_chunk(4, 4)),
            (b"EXIF", b"Exif\x00\x00" + helpers.build_tiff()),
        ]
        helpers.write(self.path, helpers.build_webp(chunks))
        data = parse_webp(self.path)
        self.assertEqual(data["exif"]["Make"], "TestCam")

    def test_file_size_reported(self):
        raw = helpers.build_webp([(b"VP8 ", helpers.build_vp8_chunk(2, 2))])
        helpers.write(self.path, raw)
        data = parse_webp(self.path)
        self.assertEqual(data["file_size"], len(raw))

    def test_rejects_non_webp(self):
        helpers.write(self.path, b"not a webp file at all")
        with self.assertRaises(UnsupportedFormatError):
            parse_webp(self.path)


if __name__ == "__main__":
    unittest.main()
