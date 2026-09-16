import os
import tempfile
import unittest

from imgmeta.errors import UnsupportedFormatError
from imgmeta.png import parse_png

from . import helpers


class PngTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        self.addCleanup(os.unlink, self.path)

    def test_ihdr_dimensions_and_color_type(self):
        helpers.write(self.path, helpers.build_png(64, 32, bit_depth=8, color_type=6))
        data = parse_png(self.path)

        self.assertEqual(data["format"], "PNG")
        self.assertEqual(data["image"]["width"], 64)
        self.assertEqual(data["image"]["height"], 32)
        self.assertEqual(data["image"]["bit_depth"], 8)
        self.assertEqual(data["image"]["color_type"], "truecolor+alpha")
        self.assertEqual(data["text"], {})

    def test_unknown_color_type_falls_back_to_raw_value(self):
        helpers.write(self.path, helpers.build_png(8, 8, color_type=99))
        data = parse_png(self.path)
        self.assertEqual(data["image"]["color_type"], 99)

    def test_text_chunk(self):
        chunks = [(b"tEXt", b"Comment\x00hello world")]
        helpers.write(self.path, helpers.build_png(1, 1, text_chunks=chunks))
        data = parse_png(self.path)
        self.assertEqual(data["text"], {"Comment": "hello world"})

    def test_ztxt_chunk_is_decompressed(self):
        chunks = [(b"zTXt", helpers.build_ztxt("Author", "someone with a fairly long name"))]
        helpers.write(self.path, helpers.build_png(1, 1, text_chunks=chunks))
        data = parse_png(self.path)
        self.assertEqual(data["text"], {"Author": "someone with a fairly long name"})

    def test_itxt_chunk_uncompressed_utf8(self):
        chunks = [(b"iTXt", helpers.build_itxt("Title", "café ☃"))]
        helpers.write(self.path, helpers.build_png(1, 1, text_chunks=chunks))
        data = parse_png(self.path)
        self.assertEqual(data["text"], {"Title": "café ☃"})

    def test_itxt_chunk_compressed_utf8(self):
        chunks = [(b"iTXt", helpers.build_itxt("Title", "compressed café", compressed=True))]
        helpers.write(self.path, helpers.build_png(1, 1, text_chunks=chunks))
        data = parse_png(self.path)
        self.assertEqual(data["text"], {"Title": "compressed café"})

    def test_multiple_text_chunks_combine(self):
        chunks = [
            (b"tEXt", b"Comment\x00hi"),
            (b"zTXt", helpers.build_ztxt("Author", "someone")),
            (b"iTXt", helpers.build_itxt("Title", "a title")),
        ]
        helpers.write(self.path, helpers.build_png(1, 1, text_chunks=chunks))
        data = parse_png(self.path)
        self.assertEqual(
            data["text"], {"Comment": "hi", "Author": "someone", "Title": "a title"}
        )

    def test_file_size_reported(self):
        raw = helpers.build_png(4, 4)
        helpers.write(self.path, raw)
        data = parse_png(self.path)
        self.assertEqual(data["file_size"], len(raw))

    def test_rejects_non_png(self):
        helpers.write(self.path, b"not a png file at all")
        with self.assertRaises(UnsupportedFormatError):
            parse_png(self.path)


if __name__ == "__main__":
    unittest.main()
