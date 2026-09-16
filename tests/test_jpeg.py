import os
import tempfile
import unittest

from imgmeta.errors import UnsupportedFormatError
from imgmeta.jpeg import parse_jpeg

from . import helpers


class JpegTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        self.addCleanup(os.unlink, self.path)

    def test_dimensions_from_sof0(self):
        helpers.write(self.path, helpers.build_jpeg(800, 600))
        data = parse_jpeg(self.path)

        self.assertEqual(data["format"], "JPEG")
        self.assertEqual(data["image"], {"width": 800, "height": 600})
        self.assertEqual(data["exif"], {})
        self.assertNotIn("gps", data)

    def test_exif_ifd0_and_subifd_tags(self):
        helpers.write(self.path, helpers.build_jpeg(4, 4, tiff=helpers.build_tiff()))
        data = parse_jpeg(self.path)

        self.assertEqual(data["exif"]["Make"], "TestCam")
        self.assertEqual(data["exif"]["Model"], "X100")
        self.assertEqual(data["exif"]["DateTimeOriginal"], "2024:06:01 14:22:03")
        self.assertAlmostEqual(data["exif"]["FNumber"], 2.8)

    def test_gps_raw_and_decimal_coordinates(self):
        helpers.write(self.path, helpers.build_jpeg(4, 4, tiff=helpers.build_tiff()))
        data = parse_jpeg(self.path)

        self.assertEqual(data["gps"]["GPSLatitudeRef"], "N")
        self.assertEqual(data["gps"]["GPSLongitudeRef"], "W")
        self.assertAlmostEqual(data["gps"]["Latitude"], 40 + 45 / 60)
        self.assertAlmostEqual(data["gps"]["Longitude"], -(73 + 59 / 60))

    def test_exif_big_endian_tiff(self):
        helpers.write(self.path, helpers.build_jpeg(4, 4, tiff=helpers.build_tiff(endian=">")))
        data = parse_jpeg(self.path)
        self.assertEqual(data["exif"]["Make"], "TestCam")
        self.assertAlmostEqual(data["gps"]["Latitude"], 40 + 45 / 60)

    def test_file_size_reported(self):
        raw = helpers.build_jpeg(10, 10)
        helpers.write(self.path, raw)
        data = parse_jpeg(self.path)
        self.assertEqual(data["file_size"], len(raw))

    def test_rejects_non_jpeg(self):
        helpers.write(self.path, b"not a jpeg file at all")
        with self.assertRaises(UnsupportedFormatError):
            parse_jpeg(self.path)


if __name__ == "__main__":
    unittest.main()
