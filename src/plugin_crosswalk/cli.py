from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .converter import convert_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plugin-crosswalk",
        description="Convert Claude marketplace plugins into cross-provider artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command")

    convert = subparsers.add_parser(
        "convert",
        help="Generate Codex-style packages and/or universal Agent Skills.",
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
        "--plugin",
        action="append",
        default=[],
        help="Limit generation to one or more Claude subplugin names.",
    )
    convert.add_argument(
        "--skip-codex",
        action="store_true",
        help="Skip Codex package generation.",
    )
    convert.add_argument(
        "--skip-agent-skills",
        action="store_true",
        help="Skip universal Agent Skills export.",
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
        plugin_names=args.plugin,
        skip_codex=args.skip_codex,
        skip_agent_skills=args.skip_agent_skills,
        clean=not args.no_clean,
    )

    print(f"Converted plugin repo into {results['output']}")
    if results["codex"]:
        print(f"Codex packages: {len(results['codex'])}")
    if results["agentSkills"]:
        print(f"Universal skills: {results['agentSkills']['count']}")
    return 0
