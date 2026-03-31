from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SUPPORT_DIRS = ("docs", "hooks", "lessons", "scripts")
SHARED_PATHS = (
    "agents/shared",
    ".claude-plugin/marketplace.json",
    "CLAUDE.md",
    "ECOSYSTEM.md",
    "LICENSE",
)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    source_dir: Path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("SKILL.md is missing valid frontmatter")

    parsed = yaml.safe_load(match.group(1))
    if not isinstance(parsed, dict):
        raise ValueError("SKILL.md frontmatter must parse to a mapping")

    return {
        str(key): "" if value is None else str(value).strip()
        for key, value in parsed.items()
    }


def discover_skills(root: Path) -> list[SkillMetadata]:
    results: list[SkillMetadata] = []
    for skill_file in sorted(root.glob("skills/**/SKILL.md")):
        metadata = parse_frontmatter(skill_file.read_text())
        name = metadata.get("name")
        description = metadata.get("description")
        if not name or not description:
            raise ValueError(f"{skill_file} is missing name/description frontmatter")
        results.append(
            SkillMetadata(
                name=name,
                description=description,
                source_dir=skill_file.parent,
            )
        )
    return results


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def title_case_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-"))


def copy_item(src_root: Path, relative_path: str, dest_root: Path) -> Path:
    src = src_root / relative_path
    dest = dest_root / relative_path
    if not src.exists():
        raise FileNotFoundError(f"Missing source path: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    return dest


def copy_if_exists(src_root: Path, relative_path: str, dest_root: Path) -> bool:
    src = src_root / relative_path
    if not src.exists():
        return False
    copy_item(src_root, relative_path, dest_root)
    return True


def build_codex_manifest(
    *,
    root_manifest: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    root_name = root_manifest["name"]
    profile_name = profile["name"]
    plugin_id = slugify(f"{root_name}-{profile_name}")
    display_name = f"{title_case_slug(root_name)} ({title_case_slug(profile_name)})"
    description = profile["description"]
    keywords = sorted(set(root_manifest.get("keywords", [])) | set(profile.get("keywords", [])))
    return {
        "name": plugin_id,
        "version": root_manifest["version"],
        "description": description,
        "author": {
            "name": root_manifest["owner"]["name"],
            "url": root_manifest.get("owner", {}).get("url", "https://github.com"),
        },
        "homepage": root_manifest.get("homepage", "https://github.com"),
        "repository": root_manifest.get("repository", "https://github.com"),
        "license": profile.get("license", root_manifest.get("license", "MIT")),
        "keywords": keywords,
        "skills": "./skills/",
        "interface": {
            "displayName": display_name,
            "shortDescription": description,
            "longDescription": (
                f"Converted from the Claude marketplace plugin '{profile_name}' "
                f"inside {root_name}. This package preserves the portable skill "
                "surface for Codex-style discovery."
            ),
            "developerName": root_manifest["owner"]["name"],
            "category": profile.get("category", "Coding").capitalize(),
            "capabilities": ["Interactive", "Write"],
            "websiteURL": root_manifest.get("homepage", "https://github.com"),
            "privacyPolicyURL": root_manifest.get("privacyPolicyURL", root_manifest.get("homepage", "https://github.com")),
            "termsOfServiceURL": root_manifest.get("termsOfServiceURL", root_manifest.get("homepage", "https://github.com")),
            "defaultPrompt": [
                f"Use the {profile_name} guidance for this task",
                "Which skills are relevant here",
                "Apply the package conventions before editing",
            ],
            "composerIcon": "",
            "logo": "",
            "screenshots": [],
        },
    }


def convert_codex_profile(
    *,
    src_root: Path,
    output_root: Path,
    root_manifest: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    root_name = root_manifest["name"]
    profile_name = profile["name"]
    plugin_id = slugify(f"{root_name}-{profile_name}")
    package_root = output_root / plugin_id

    copied: dict[str, list[str]] = {"skills": [], "commands": [], "agents": []}

    for relative in profile.get("skills", []):
        copy_item(src_root, relative, package_root)
        copied["skills"].append(relative)

    for relative in profile.get("commands", []):
        copy_item(src_root, relative, package_root)
        copied["commands"].append(relative)

    for relative in profile.get("agents", []):
        copy_item(src_root, relative, package_root)
        copied["agents"].append(relative)

    for relative in SHARED_PATHS:
        copy_if_exists(src_root, relative, package_root)

    for directory in SUPPORT_DIRS:
        copy_if_exists(src_root, directory, package_root)

    manifest = build_codex_manifest(root_manifest=root_manifest, profile=profile)
    write_json(package_root / ".codex-plugin" / "plugin.json", manifest)
    write_json(
        package_root / "conversion-summary.json",
        {
            "sourcePlugin": root_name,
            "sourceProfile": profile_name,
            "outputPluginId": plugin_id,
            "copied": copied,
        },
    )
    write_text(
        package_root / "README.md",
        "\n".join(
            [
                f"# {manifest['interface']['displayName']}",
                "",
                f"Converted from `{root_name}` / `{profile_name}` by `plugin-crosswalk`.",
                "",
                "## Included",
                "",
                f"- Skills: {len(copied['skills'])}",
                f"- Commands copied for source parity: {len(copied['commands'])}",
                f"- Agents copied for source parity: {len(copied['agents'])}",
                "",
                "## Notes",
                "",
                "- Codex-native discovery is expected to work for the copied `skills/` tree.",
                "- Commands, hooks, and agent orchestration are copied as source material, but may still require host-specific runtime integration.",
                "",
            ]
        ),
    )
    return {
        "profile": profile_name,
        "plugin_id": plugin_id,
        "path": str(package_root),
        "counts": {kind: len(items) for kind, items in copied.items()},
    }


def build_agents_catalog(exported_skills: list[dict[str, str]], universal_root: Path) -> str:
    lines = [
        "# Cross-Provider Skill Catalog",
        "",
        "These skills were exported into `.agents/skills/` for cross-client discovery.",
        "",
        "<available_skills>",
    ]
    for skill in exported_skills:
        location = universal_root / ".agents" / "skills" / skill["exportedAs"] / "SKILL.md"
        description = " ".join(skill["description"].split())
        lines.extend(
            [
                "  <skill>",
                f"    <name>{skill['name']}</name>",
                f"    <description>{description}</description>",
                f"    <location>{location}</location>",
                "  </skill>",
            ]
        )
    lines.extend(["</available_skills>", ""])
    return "\n".join(lines)


def convert_agent_skills(
    *,
    src_root: Path,
    output_root: Path,
    discovered_skills: list[SkillMetadata],
) -> dict[str, Any]:
    universal_root = output_root / "universal"
    skill_root = universal_root / ".agents" / "skills"

    collisions: dict[str, int] = {}
    exported: list[dict[str, str]] = []

    for skill in discovered_skills:
        target_name = skill.name
        if (skill_root / target_name).exists():
            collisions[target_name] = collisions.get(target_name, 0) + 1
            target_name = f"{target_name}-{collisions[target_name] + 1}"

        destination = skill_root / target_name
        shutil.copytree(skill.source_dir, destination)
        exported.append(
            {
                "name": skill.name,
                "description": skill.description,
                "exportedAs": target_name,
                "source": str(skill.source_dir.relative_to(src_root)),
                "destination": str(destination),
            }
        )

    write_text(universal_root / "AGENTS.md", build_agents_catalog(exported, universal_root))
    write_json(universal_root / "skills-index.json", {"skills": exported})
    return {"path": str(universal_root), "count": len(exported)}


def convert_repository(
    *,
    root: Path,
    output: Path,
    plugin_names: list[str] | None = None,
    skip_codex: bool = False,
    skip_agent_skills: bool = False,
    clean: bool = True,
) -> dict[str, Any]:
    src_root = root.resolve()
    output_root = output.resolve()

    manifest_path = src_root / ".claude-plugin" / "marketplace.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing Claude marketplace manifest: {manifest_path}")

    root_manifest = read_json(manifest_path)
    profiles = root_manifest.get("plugins", [])
    if plugin_names:
        wanted = set(plugin_names)
        profiles = [profile for profile in profiles if profile["name"] in wanted]
        missing = wanted - {profile["name"] for profile in profiles}
        if missing:
            raise ValueError(f"Unknown plugin names: {', '.join(sorted(missing))}")

    if output_root.exists() and clean:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "source": str(src_root),
        "output": str(output_root),
        "codex": [],
        "agentSkills": None,
    }

    if not skip_codex:
        codex_root = output_root / "codex"
        for profile in profiles:
            results["codex"].append(
                convert_codex_profile(
                    src_root=src_root,
                    output_root=codex_root,
                    root_manifest=root_manifest,
                    profile=profile,
                )
            )

    if not skip_agent_skills:
        discovered_skills = discover_skills(src_root)
        results["agentSkills"] = convert_agent_skills(
            src_root=src_root,
            output_root=output_root,
            discovered_skills=discovered_skills,
        )

    write_json(output_root / "conversion-report.json", results)
    return results
