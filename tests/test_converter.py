from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from plugin_crosswalk.converter import convert_repository, parse_frontmatter


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_claude_plugin"


def test_parse_frontmatter_supports_multiline_description() -> None:
    text = (FIXTURE_ROOT / "skills" / "development" / "multi-line-skill" / "SKILL.md").read_text()
    parsed = parse_frontmatter(text)

    assert parsed["name"] == "multi-line"
    assert parsed["description"] == (
        "Multi-line description for a fixture skill.\n"
        "Second sentence stays part of the same value."
    )


def test_convert_repository_generates_codex_package(tmp_path: Path) -> None:
    results = convert_repository(
        root=FIXTURE_ROOT,
        output=tmp_path / "out",
        plugin_names=["complete"],
        skip_agent_skills=True,
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
        root=FIXTURE_ROOT,
        output=tmp_path / "out",
        skip_codex=True,
    )

    assert results["agentSkills"]["count"] == 2
    catalog = (tmp_path / "out" / "universal" / "AGENTS.md").read_text()
    assert "<name>multi-line</name>" in catalog
    assert "Multi-line description for a fixture skill. Second sentence stays part of the same value." in catalog


def test_cli_convert_smoke(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "plugin_crosswalk",
            "convert",
            "--root",
            str(FIXTURE_ROOT),
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
            str(FIXTURE_ROOT),
            "--output",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Universal skills: 2" in proc.stdout
