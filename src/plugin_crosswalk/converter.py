from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


FormatName = Literal["claude", "codex", "universal"]
FORMAT_ORDER: tuple[FormatName, ...] = ("claude", "codex", "universal")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
CLAUDE_SUPPORT_PATHS = (
    "agents/shared",
    ".claude-plugin/marketplace.json",
    "CLAUDE.md",
    "ECOSYSTEM.md",
    "LICENSE",
    "README.md",
    ".mcp.json",
)
CODEX_SUPPORT_PATHS = (
    ".codex-plugin/plugin.json",
    "LICENSE",
    "README.md",
    ".mcp.json",
)
SUPPORT_DIRS = ("docs", "hooks", "lessons", "scripts")


@dataclass(frozen=True)
class SkillAsset:
    name: str
    description: str
    source_rel: str
    target_rel: str


@dataclass(frozen=True)
class FileAsset:
    source_rel: str
    target_rel: str


@dataclass(frozen=True)
class ProfileModel:
    name: str
    description: str
    category: str
    version: str
    license: str
    keywords: list[str] = field(default_factory=list)
    skills: list[SkillAsset] = field(default_factory=list)
    commands: list[FileAsset] = field(default_factory=list)
    agents: list[FileAsset] = field(default_factory=list)


@dataclass(frozen=True)
class RepositoryModel:
    source_format: FormatName
    name: str
    version: str
    description: str
    owner_name: str
    owner_url: str
    homepage: str
    repository: str
    license: str
    profiles: list[ProfileModel]
    support_assets: list[FileAsset] = field(default_factory=list)


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


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def title_case_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-"))


def normalize_relative_path(value: str) -> str:
    value = value.strip()
    if value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def detect_source_format(root: Path) -> FormatName:
    codex_manifest = root / ".codex-plugin" / "plugin.json"
    claude_manifest = root / ".claude-plugin" / "marketplace.json"
    universal_root = resolve_universal_skill_root(root)

    if codex_manifest.exists():
        return "codex"
    if claude_manifest.exists():
        return "claude"
    if universal_root is not None:
        return "universal"
    raise ValueError(
        "Could not detect source format. Expected one of: "
        ".claude-plugin/marketplace.json, .codex-plugin/plugin.json, or .agents/skills."
    )


def resolve_universal_skill_root(root: Path) -> Path | None:
    if (root / ".agents" / "skills").is_dir():
        return root / ".agents" / "skills"
    if root.name == "skills" and root.parent.name == ".agents":
        return root
    return None


def discover_support_assets(root: Path, candidates: tuple[str, ...]) -> list[FileAsset]:
    assets: list[FileAsset] = []
    seen: set[str] = set()

    for relative in candidates:
        source = root / relative
        if not source.exists():
            continue
        normalized = normalize_relative_path(relative)
        seen.add(normalized)
        assets.append(FileAsset(source_rel=normalized, target_rel=normalized))

    for directory in SUPPORT_DIRS:
        source = root / directory
        if not source.exists():
            continue
        normalized = normalize_relative_path(directory)
        if normalized in seen:
            continue
        seen.add(normalized)
        assets.append(FileAsset(source_rel=normalized, target_rel=normalized))

    return assets


def discover_skill_assets_from_root(root: Path, skill_root_rel: str) -> list[SkillAsset]:
    skill_root = root / normalize_relative_path(skill_root_rel)
    assets: list[SkillAsset] = []
    for skill_file in sorted(skill_root.glob("**/SKILL.md")):
        metadata = parse_frontmatter(skill_file.read_text())
        name = metadata.get("name")
        description = metadata.get("description")
        if not name or not description:
            raise ValueError(f"{skill_file} is missing name/description frontmatter")
        skill_dir = skill_file.parent
        relative_dir = str(skill_dir.relative_to(root))
        assets.append(
            SkillAsset(
                name=name,
                description=description,
                source_rel=relative_dir,
                target_rel=relative_dir,
            )
        )
    return assets


def dedupe_skill_targets(assets: list[SkillAsset], prefix: str) -> list[SkillAsset]:
    used: set[str] = set()
    deduped: list[SkillAsset] = []
    for asset in assets:
        base_name = slugify(asset.name) or "skill"
        candidate = f"{prefix}/{base_name}"
        suffix = 2
        while candidate in used:
            candidate = f"{prefix}/{base_name}-{suffix}"
            suffix += 1
        used.add(candidate)
        deduped.append(
            SkillAsset(
                name=asset.name,
                description=asset.description,
                source_rel=asset.source_rel,
                target_rel=candidate,
            )
        )
    return deduped


def discover_markdown_assets(root: Path, pattern: str, exclude_prefixes: tuple[str, ...] = ()) -> list[FileAsset]:
    assets: list[FileAsset] = []
    for path in sorted(root.glob(pattern)):
        relative = str(path.relative_to(root))
        if any(relative.startswith(prefix) for prefix in exclude_prefixes):
            continue
        assets.append(FileAsset(source_rel=relative, target_rel=relative))
    return assets


def derive_universal_package_name(root: Path, skill_root: Path) -> str:
    if skill_root == root / ".agents" / "skills":
        base = root.name
    else:
        base = root.parent.parent.name
    return slugify(base) or "agent-skills"


def read_claude_repository(root: Path) -> RepositoryModel:
    manifest = read_json(root / ".claude-plugin" / "marketplace.json")
    profiles: list[ProfileModel] = []

    for profile in manifest.get("plugins", []):
        skills = [
            SkillAsset(
                name=parse_frontmatter((root / normalize_relative_path(relative) / "SKILL.md").read_text())["name"],
                description=parse_frontmatter((root / normalize_relative_path(relative) / "SKILL.md").read_text())["description"],
                source_rel=normalize_relative_path(relative),
                target_rel=normalize_relative_path(relative),
            )
            for relative in profile.get("skills", [])
        ]
        commands = [
            FileAsset(
                source_rel=normalize_relative_path(relative),
                target_rel=normalize_relative_path(relative),
            )
            for relative in profile.get("commands", [])
        ]
        agents = [
            FileAsset(
                source_rel=normalize_relative_path(relative),
                target_rel=normalize_relative_path(relative),
            )
            for relative in profile.get("agents", [])
        ]
        profiles.append(
            ProfileModel(
                name=profile["name"],
                description=profile["description"],
                category=profile.get("category", "coding"),
                version=profile.get("version", manifest["version"]),
                license=profile.get("license", manifest.get("license", "MIT")),
                keywords=list(profile.get("keywords", [])),
                skills=skills,
                commands=commands,
                agents=agents,
            )
        )

    return RepositoryModel(
        source_format="claude",
        name=manifest["name"],
        version=manifest["version"],
        description=manifest["description"],
        owner_name=manifest.get("owner", {}).get("name", manifest["name"]),
        owner_url=manifest.get("owner", {}).get("url", ""),
        homepage=manifest.get("homepage", ""),
        repository=manifest.get("repository", ""),
        license=manifest.get("license", "MIT"),
        profiles=profiles,
        support_assets=discover_support_assets(root, CLAUDE_SUPPORT_PATHS),
    )


def read_codex_repository(root: Path) -> RepositoryModel:
    manifest = read_json(root / ".codex-plugin" / "plugin.json")
    skills_path = manifest.get("skills", "./skills/")
    skills = discover_skill_assets_from_root(root, skills_path)
    commands = discover_markdown_assets(root, "commands/**/*.md")
    agents = discover_markdown_assets(root, "agents/**/*.md", exclude_prefixes=("agents/shared/",))
    category = manifest.get("interface", {}).get("category", "coding").lower()

    profile = ProfileModel(
        name="complete",
        description=manifest["description"],
        category=category,
        version=manifest.get("version", "0.1.0"),
        license=manifest.get("license", "MIT"),
        keywords=list(manifest.get("keywords", [])),
        skills=skills,
        commands=commands,
        agents=agents,
    )

    author = manifest.get("author", {})
    return RepositoryModel(
        source_format="codex",
        name=manifest["name"],
        version=manifest.get("version", "0.1.0"),
        description=manifest["description"],
        owner_name=author.get("name", manifest["name"]),
        owner_url=author.get("url", ""),
        homepage=manifest.get("homepage", ""),
        repository=manifest.get("repository", ""),
        license=manifest.get("license", "MIT"),
        profiles=[profile],
        support_assets=discover_support_assets(root, CODEX_SUPPORT_PATHS),
    )


def read_universal_repository(root: Path) -> RepositoryModel:
    skill_root = resolve_universal_skill_root(root)
    if skill_root is None:
        raise ValueError("Universal source must contain .agents/skills or point directly at that directory")

    assets: list[SkillAsset] = []
    for skill_file in sorted(skill_root.glob("**/SKILL.md")):
        metadata = parse_frontmatter(skill_file.read_text())
        name = metadata.get("name")
        description = metadata.get("description")
        if not name or not description:
            raise ValueError(f"{skill_file} is missing name/description frontmatter")
        assets.append(
            SkillAsset(
                name=name,
                description=description,
                source_rel=str(skill_file.parent.relative_to(root)),
                target_rel="",
            )
        )

    package_name = derive_universal_package_name(root, skill_root)
    profile = ProfileModel(
        name="complete",
        description=f"Universal Agent Skills sourced from {package_name}",
        category="coding",
        version="0.1.0",
        license="MIT",
        keywords=["skills", "agents"],
        skills=dedupe_skill_targets(assets, "skills"),
    )

    support_assets: list[FileAsset] = []
    if (root / "AGENTS.md").exists():
        support_assets.append(FileAsset(source_rel="AGENTS.md", target_rel="AGENTS.md"))

    return RepositoryModel(
        source_format="universal",
        name=package_name,
        version="0.1.0",
        description=f"Universal Agent Skills package sourced from {package_name}",
        owner_name="plugin-crosswalk",
        owner_url="https://github.com/MaxGhenis/plugin-crosswalk",
        homepage="https://github.com/MaxGhenis/plugin-crosswalk",
        repository="https://github.com/MaxGhenis/plugin-crosswalk",
        license="MIT",
        profiles=[profile],
        support_assets=support_assets,
    )


def load_repository(root: Path, source_format: FormatName) -> RepositoryModel:
    if source_format == "claude":
        return read_claude_repository(root)
    if source_format == "codex":
        return read_codex_repository(root)
    if source_format == "universal":
        return read_universal_repository(root)
    raise ValueError(f"Unsupported source format: {source_format}")


def copy_asset(src_root: Path, source_rel: str, dest_root: Path, target_rel: str) -> None:
    source = src_root / source_rel
    target = dest_root / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def build_codex_manifest(*, model: RepositoryModel, profile: ProfileModel) -> dict[str, Any]:
    plugin_id = slugify(f"{model.name}-{profile.name}")
    display_name = f"{title_case_slug(model.name)} ({title_case_slug(profile.name)})"
    keywords = sorted(set(profile.keywords))
    return {
        "name": plugin_id,
        "version": profile.version,
        "description": profile.description,
        "author": {
            "name": model.owner_name,
            "url": model.owner_url or model.repository or model.homepage or "https://github.com",
        },
        "homepage": model.homepage or model.repository or "https://github.com",
        "repository": model.repository or model.homepage or "https://github.com",
        "license": profile.license,
        "keywords": keywords,
        "skills": "./skills/",
        "interface": {
            "displayName": display_name,
            "shortDescription": profile.description,
            "longDescription": (
                f"Converted from the {model.source_format} source '{model.name}' "
                f"for the profile '{profile.name}'."
            ),
            "developerName": model.owner_name,
            "category": profile.category.capitalize(),
            "capabilities": ["Interactive", "Write"],
            "websiteURL": model.homepage or model.repository or "https://github.com",
            "privacyPolicyURL": model.homepage or model.repository or "https://github.com",
            "termsOfServiceURL": model.homepage or model.repository or "https://github.com",
            "defaultPrompt": [
                f"Use the {profile.name} guidance for this task",
                "Which skills are relevant here",
                "Apply the package conventions before editing",
            ],
            "composerIcon": "",
            "logo": "",
            "screenshots": [],
        },
    }


def emit_codex_repository(model: RepositoryModel, src_root: Path, output_root: Path) -> list[dict[str, Any]]:
    codex_root = output_root / "codex"
    outputs: list[dict[str, Any]] = []

    for profile in model.profiles:
        plugin_id = slugify(f"{model.name}-{profile.name}")
        package_root = codex_root / plugin_id

        copied = {"skills": [], "commands": [], "agents": [], "support": []}

        for skill in profile.skills:
            copy_asset(src_root, skill.source_rel, package_root, skill.target_rel)
            copied["skills"].append(skill.target_rel)

        for asset in profile.commands:
            copy_asset(src_root, asset.source_rel, package_root, asset.target_rel)
            copied["commands"].append(asset.target_rel)

        for asset in profile.agents:
            copy_asset(src_root, asset.source_rel, package_root, asset.target_rel)
            copied["agents"].append(asset.target_rel)

        for asset in model.support_assets:
            copy_asset(src_root, asset.source_rel, package_root, asset.target_rel)
            copied["support"].append(asset.target_rel)

        manifest = build_codex_manifest(model=model, profile=profile)
        write_json(package_root / ".codex-plugin" / "plugin.json", manifest)
        write_json(
            package_root / "conversion-summary.json",
            {
                "sourceFormat": model.source_format,
                "sourceName": model.name,
                "sourceProfile": profile.name,
                "outputPluginId": plugin_id,
                "copied": copied,
            },
        )
        outputs.append(
            {
                "profile": profile.name,
                "plugin_id": plugin_id,
                "path": str(package_root),
                "counts": {kind: len(items) for kind, items in copied.items()},
            }
        )

    return outputs


def build_claude_manifest(model: RepositoryModel) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile in model.profiles:
        profiles.append(
            {
                "name": profile.name,
                "description": profile.description,
                "source": "./",
                "category": profile.category,
                "version": profile.version,
                "keywords": profile.keywords,
                "author": {
                    "name": model.owner_name,
                    "url": model.owner_url or model.repository or model.homepage or "https://github.com",
                },
                "license": profile.license,
                "skills": [f"./{skill.target_rel}" for skill in profile.skills],
                "commands": [f"./{asset.target_rel}" for asset in profile.commands] or None,
                "agents": [f"./{asset.target_rel}" for asset in profile.agents] or None,
            }
        )
        if profiles[-1]["commands"] is None:
            del profiles[-1]["commands"]
        if profiles[-1]["agents"] is None:
            del profiles[-1]["agents"]

    return {
        "$schema": "https://claude.ai/schemas/plugin-marketplace.json",
        "name": model.name,
        "version": model.version,
        "description": model.description,
        "homepage": model.homepage,
        "repository": model.repository,
        "license": model.license,
        "owner": {
            "name": model.owner_name,
            "url": model.owner_url,
        },
        "plugins": profiles,
    }


def emit_claude_repository(model: RepositoryModel, src_root: Path, output_root: Path) -> dict[str, Any]:
    package_root = output_root / "claude" / model.name
    copied = {"skills": [], "commands": [], "agents": [], "support": []}

    for profile in model.profiles:
        for skill in profile.skills:
            copy_asset(src_root, skill.source_rel, package_root, skill.target_rel)
            copied["skills"].append(skill.target_rel)
        for asset in profile.commands:
            copy_asset(src_root, asset.source_rel, package_root, asset.target_rel)
            copied["commands"].append(asset.target_rel)
        for asset in profile.agents:
            copy_asset(src_root, asset.source_rel, package_root, asset.target_rel)
            copied["agents"].append(asset.target_rel)

    for asset in model.support_assets:
        if asset.target_rel == ".claude-plugin/marketplace.json":
            continue
        copy_asset(src_root, asset.source_rel, package_root, asset.target_rel)
        copied["support"].append(asset.target_rel)

    write_json(package_root / ".claude-plugin" / "marketplace.json", build_claude_manifest(model))
    write_json(
        package_root / "conversion-summary.json",
        {
            "sourceFormat": model.source_format,
            "sourceName": model.name,
            "profileCount": len(model.profiles),
            "copied": {kind: len(items) for kind, items in copied.items()},
        },
    )
    return {
        "path": str(package_root),
        "profileCount": len(model.profiles),
        "counts": {kind: len(items) for kind, items in copied.items()},
    }


def build_agents_catalog(skills: list[dict[str, str]], universal_root: Path) -> str:
    lines = [
        "# Cross-Provider Skill Catalog",
        "",
        "These skills were exported into `.agents/skills/` for cross-client discovery.",
        "",
        "<available_skills>",
    ]
    for skill in skills:
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


def emit_universal_skills(model: RepositoryModel, src_root: Path, output_root: Path) -> dict[str, Any]:
    universal_root = output_root / "universal"
    skill_root = universal_root / ".agents" / "skills"
    exported: list[dict[str, str]] = []
    used: set[str] = set()
    seen_source_rels: set[str] = set()

    for profile in model.profiles:
        for skill in profile.skills:
            if skill.source_rel in seen_source_rels:
                continue
            seen_source_rels.add(skill.source_rel)
            exported_name = slugify(skill.name) or Path(skill.target_rel).name or "skill"
            candidate = exported_name
            suffix = 2
            while candidate in used:
                candidate = f"{exported_name}-{suffix}"
                suffix += 1
            used.add(candidate)
            destination = skill_root / candidate
            shutil.copytree(src_root / skill.source_rel, destination)
            exported.append(
                {
                    "name": skill.name,
                    "description": skill.description,
                    "exportedAs": candidate,
                    "source": skill.source_rel,
                    "destination": str(destination),
                }
            )

    write_text(universal_root / "AGENTS.md", build_agents_catalog(exported, universal_root))
    write_json(universal_root / "skills-index.json", {"skills": exported})
    return {"path": str(universal_root), "count": len(exported)}


def normalize_target_list(source_format: FormatName, targets: list[FormatName] | None) -> list[FormatName]:
    if targets:
        ordered: list[FormatName] = []
        seen: set[FormatName] = set()
        for target in targets:
            if target not in seen:
                ordered.append(target)
                seen.add(target)
        return ordered
    return [target for target in FORMAT_ORDER if target != source_format]


def convert_repository(
    *,
    root: Path,
    output: Path,
    source_format: FormatName | Literal["auto"] = "auto",
    targets: list[FormatName] | None = None,
    plugin_names: list[str] | None = None,
    clean: bool = True,
) -> dict[str, Any]:
    src_root = root.resolve()
    inferred_format = detect_source_format(src_root) if source_format == "auto" else source_format
    model = load_repository(src_root, inferred_format)

    if plugin_names and inferred_format != "claude":
        raise ValueError("--plugin is currently only supported for Claude sources")
    if plugin_names:
        wanted = set(plugin_names)
        filtered_profiles = [profile for profile in model.profiles if profile.name in wanted]
        missing = wanted - {profile.name for profile in filtered_profiles}
        if missing:
            raise ValueError(f"Unknown plugin names: {', '.join(sorted(missing))}")
        model = RepositoryModel(
            source_format=model.source_format,
            name=model.name,
            version=model.version,
            description=model.description,
            owner_name=model.owner_name,
            owner_url=model.owner_url,
            homepage=model.homepage,
            repository=model.repository,
            license=model.license,
            profiles=filtered_profiles,
            support_assets=model.support_assets,
        )

    output_root = output.resolve()
    if output_root.exists() and clean:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    normalized_targets = normalize_target_list(inferred_format, targets)
    results: dict[str, Any] = {
        "source": str(src_root),
        "sourceFormat": inferred_format,
        "output": str(output_root),
        "targets": normalized_targets,
        "claude": None,
        "codex": [],
        "universal": None,
        "agentSkills": None,
    }

    for target in normalized_targets:
        if target == "codex":
            results["codex"] = emit_codex_repository(model, src_root, output_root)
        elif target == "claude":
            results["claude"] = emit_claude_repository(model, src_root, output_root)
        elif target == "universal":
            universal = emit_universal_skills(model, src_root, output_root)
            results["universal"] = universal
            results["agentSkills"] = universal
        else:
            raise ValueError(f"Unsupported target format: {target}")

    write_json(output_root / "conversion-report.json", results)
    return results
