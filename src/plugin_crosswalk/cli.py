from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .converter import FORMAT_ORDER, FormatName, convert_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plugin-crosswalk",
        description="Convert Claude marketplace plugins into cross-provider artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command")

    convert = subparsers.add_parser(
        "convert",
        help="Generate Claude, Codex, and/or universal Agent Skills outputs.",
    )
    convert.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Source plugin repository root. Defaults to the current directory.",
    )
    convert.add_argument(
        "--output",
        type=Path,
        default=Path("dist/cross-provider"),
        help="Output directory. Defaults to dist/cross-provider.",
    )
    convert.add_argument(
        "--from",
        dest="source_format",
        choices=["auto", *FORMAT_ORDER],
        default="auto",
        help="Source format. Defaults to auto-detect.",
    )
    convert.add_argument(
        "--to",
        dest="targets",
        action="append",
        choices=list(FORMAT_ORDER),
        default=[],
        help="Target format. Repeat to generate multiple outputs. Defaults to all other formats.",
    )
    convert.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Limit generation to one or more Claude subplugin names. Claude sources only.",
    )
    convert.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete the output directory before writing new files.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0].startswith("-"):
        args_list = ["convert", *args_list]

    args = parser.parse_args(args_list)
    command = args.command
    if command != "convert":
        parser.error(f"Unknown command: {command}")

    results = convert_repository(
        root=args.root,
        output=args.output,
        source_format=args.source_format,
        targets=list(args.targets) if args.targets else None,
        plugin_names=args.plugin,
        clean=not args.no_clean,
    )

    print(f"Converted {results['sourceFormat']} source into {results['output']}")
    if results["claude"]:
        print("Claude output: 1")
    if results["codex"]:
        print(f"Codex packages: {len(results['codex'])}")
    if results["universal"]:
        print(f"Universal skills: {results['universal']['count']}")
    return 0
