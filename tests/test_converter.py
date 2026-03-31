from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from plugin_crosswalk.converter import convert_repository, parse_frontmatter


FIXTURES = Path(__file__).parent / "fixtures"
CLAUDE_FIXTURE = FIXTURES / "sample_claude_plugin"
CODEX_FIXTURE = FIXTURES / "sample_codex_plugin"
UNIVERSAL_FIXTURE = FIXTURES / "sample_universal_skills"


def test_parse_frontmatter_supports_multiline_description() -> None:
    text = (CLAUDE_FIXTURE / "skills" / "development" / "multi-line-skill" / "SKILL.md").read_text()
    parsed = parse_frontmatter(text)

    assert parsed["name"] == "multi-line"
    assert parsed["description"] == (
        "Multi-line description for a fixture skill.\n"
        "Second sentence stays part of the same value."
    )


def test_convert_repository_generates_codex_package(tmp_path: Path) -> None:
    results = convert_repository(
        root=CLAUDE_FIXTURE,
        output=tmp_path / "out",
        source_format="claude",
        targets=["codex"],
        plugin_names=["complete"],
    )

    assert len(results["codex"]) == 1
    plugin_root = tmp_path / "out" / "codex" / "sample-plugin-complete"
    manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text())

    assert manifest["name"] == "sample-plugin-complete"
    assert manifest["version"] == "1.2.3"
    assert (plugin_root / "skills" / "development" / "multi-line-skill" / "SKILL.md").exists()
    assert (plugin_root / "commands" / "do-the-thing.md").exists()
    assert (plugin_root / "agents" / "reviewer.md").exists()
    assert (plugin_root / "agents" / "shared" / "standards.md").exists()
    assert (plugin_root / "scripts" / "helper.sh").exists()


def test_convert_repository_generates_universal_skill_catalog(tmp_path: Path) -> None:
    results = convert_repository(
        root=CLAUDE_FIXTURE,
        output=tmp_path / "out",
        source_format="claude",
        targets=["universal"],
    )

    assert results["universal"]["count"] == 2
    catalog = (tmp_path / "out" / "universal" / "AGENTS.md").read_text()
    assert "<name>multi-line</name>" in catalog
    assert "Multi-line description for a fixture skill. Second sentence stays part of the same value." in catalog


def test_convert_codex_source_generates_claude_and_universal(tmp_path: Path) -> None:
    results = convert_repository(
        root=CODEX_FIXTURE,
        output=tmp_path / "out",
        targets=["claude", "universal"],
    )

    assert results["sourceFormat"] == "codex"
    assert results["claude"] is not None
    manifest = json.loads((tmp_path / "out" / "claude" / "sample-codex" / ".claude-plugin" / "marketplace.json").read_text())
    assert manifest["name"] == "sample-codex"
    assert manifest["plugins"][0]["name"] == "complete"
    assert results["universal"]["count"] == 1


def test_convert_universal_source_generates_claude_and_codex(tmp_path: Path) -> None:
    results = convert_repository(
        root=UNIVERSAL_FIXTURE,
        output=tmp_path / "out",
    )

    assert results["sourceFormat"] == "universal"
    claude_manifest = json.loads((tmp_path / "out" / "claude" / "sample-universal-skills" / ".claude-plugin" / "marketplace.json").read_text())
    assert claude_manifest["name"] == "sample-universal-skills"
    assert len(results["codex"]) == 1
    codex_manifest = json.loads((tmp_path / "out" / "codex" / "sample-universal-skills-complete" / ".codex-plugin" / "plugin.json").read_text())
    assert codex_manifest["name"] == "sample-universal-skills-complete"


def test_cli_convert_smoke(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "plugin_crosswalk",
            "convert",
            "--root",
            str(CLAUDE_FIXTURE),
            "--output",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Codex packages: 2" in proc.stdout
    assert (output_dir / "conversion-report.json").exists()


def test_cli_default_command_smoke(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "plugin_crosswalk",
            "--root",
            str(CLAUDE_FIXTURE),
            "--output",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Universal skills: 2" in proc.stdout


def test_cli_codex_to_claude_smoke(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "plugin_crosswalk",
            "convert",
            "--root",
            str(CODEX_FIXTURE),
            "--to",
            "claude",
            "--output",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Claude output: 1" in proc.stdout
