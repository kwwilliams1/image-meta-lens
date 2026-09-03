"""Demo entry point: `python -m imgmeta some.jpg other.png --json`.

Not installed as a console script on purpose -- this is a library, and this
module exists so the parsers can be poked at from the command line without
writing a throwaway script every time.
"""

import argparse
import json
import sys

from . import UnsupportedFormatError, format_human, read_metadata


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m imgmeta",
        description="Print image metadata as human-readable text or JSON.",
    )
    parser.add_argument("paths", nargs="+", help="image files to inspect")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a JSON array instead of the human-readable summary",
    )
    args = parser.parse_args(argv)

    results = []
    exit_code = 0
    for path in args.paths:
        try:
            results.append(read_metadata(path))
        except (OSError, UnsupportedFormatError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            exit_code = 1

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        for metadata in results:
            print(format_human(metadata))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
