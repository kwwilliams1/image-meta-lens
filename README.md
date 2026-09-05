# imgmeta

Reads dimensions, EXIF camera fields, and PNG text chunks out of image
files. Pure standard library, no dependencies.

## Why

Most of the time when a script needs "what camera took this" or "what size
is this image" it doesn't need a whole imaging library, it needs a couple
of fields out of a header. Pulling in Pillow (or a compiled exif library)
for that is a lot of dependency weight and build-toolchain risk for a
handful of struct.unpack calls. This library does just the parsing: JPEG
markers and the Exif APP1 segment, PNG chunks. No image decoding, no
resizing, no writing files back out.

## Supported formats

- JPEG: width/height from the SOF marker, plus Make, Model, Orientation,
  Software, DateTime, ExposureTime, FNumber, ISOSpeedRatings,
  DateTimeOriginal, and FocalLength from the Exif segment when present.
- PNG: width/height/bit depth/color type from IHDR, plus any `tEXt`,
  `zTXt`, or `iTXt` key/value pairs (compressed and international text
  chunks are decompressed/decoded, not just skipped).

Anything else raises `imgmeta.UnsupportedFormatError`.

## Usage

```python
import imgmeta

data = imgmeta.read_metadata("vacation.jpg")
print(data["image"])   # {'width': 4032, 'height': 3024}
print(data["exif"])    # {'Make': 'Apple', 'Model': 'iPhone 13', ...}

print(imgmeta.format_human(data))
print(imgmeta.format_json(data))
```

`read_metadata` returns a plain dict:

```python
{
    "path": "vacation.jpg",
    "format": "JPEG",
    "file_size": 3145211,
    "image": {"width": 4032, "height": 3024},
    "exif": {"Make": "Apple", "Model": "iPhone 13", "DateTimeOriginal": "2024:06:01 14:22:03"},
}
```

For PNGs the shape is the same except `exif` is replaced with `text`,
holding whatever `tEXt`/`zTXt`/`iTXt` chunks were embedded (things like
`Comment` or software-specific keys).

### Command line

There's no installed executable, but the package can be run as a module
for quick checks:

```
$ python -m imgmeta vacation.jpg logo.png
vacation.jpg (JPEG, 3145211 bytes)
  4032x3024
  exif:
    DateTimeOriginal: 2024:06:01 14:22:03
    Make: Apple
    Model: iPhone 13

logo.png (PNG, 8422 bytes)
  512x512, truecolor+alpha, 8-bit

$ python -m imgmeta --json vacation.jpg
[
  {
    "exif": {
      "DateTimeOriginal": "2024:06:01 14:22:03",
      "Make": "Apple",
      "Model": "iPhone 13"
    },
    "file_size": 3145211,
    "format": "JPEG",
    "image": {
      "height": 3024,
      "width": 4032
    },
    "path": "vacation.jpg"
  }
]
```

## Install

Not published anywhere yet. Copy the `imgmeta/` package into your project,
or install it locally in editable mode:

```
pip install -e .
```

## License

MIT, see LICENSE.
