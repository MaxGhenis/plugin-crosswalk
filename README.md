# plugin-crosswalk

`plugin-crosswalk` converts between three plugin/skill layouts:

- Claude marketplace plugin repos
- Codex-style plugin packages with `.codex-plugin/plugin.json`
- Universal `.agents/skills` exports for cross-client skill loading

It is intentionally conservative about runtime parity. Skills convert well.
Provider-specific hooks, slash commands, and subagent execution logic are copied
for source parity, but may still need host-specific integration.

## Why this exists

There are now real interoperability layers for parts of the stack:

- MCP for tools and remote integrations
- `SKILL.md`-style Agent Skills for reusable instruction packages

What is still missing is a robust converter from a provider-native marketplace
plugin into another provider's package layout. This project fills that gap for
the portable subset first.

## Install

```bash
uv tool install .
```

Or for development:

```bash
uv sync --dev
```

## CLI

Auto-detect the source format and generate all other target formats:

```bash
plugin-crosswalk convert
```

Convert a specific Claude subplugin into Codex only:

```bash
plugin-crosswalk convert --root /path/to/plugin --from claude --to codex --plugin app-development
```

Convert a Codex package back into a Claude repo:

```bash
plugin-crosswalk convert --root /path/to/codex-package --from codex --to claude
```

Convert universal skills into both Claude and Codex outputs:

```bash
plugin-crosswalk convert --root /path/to/repo-with-.agents
```

Write without cleaning the existing output directory first:

```bash
plugin-crosswalk convert --no-clean
```

## Output layout

```text
dist/cross-provider/
├── claude/
│   └── <plugin-name>/
│       ├── .claude-plugin/marketplace.json
│       ├── skills/
│       ├── commands/
│       └── agents/
├── codex/
│   └── <plugin-id>/
│       ├── .codex-plugin/plugin.json
│       ├── skills/
│       ├── commands/
│       └── agents/
└── universal/
    ├── AGENTS.md
    └── .agents/skills/
```

## Development

Run tests:

```bash
uv run pytest
```

The repository includes fixture-based tests for:

- multiline YAML frontmatter parsing
- Claude -> Codex conversion
- Claude -> universal conversion
- Codex -> Claude conversion
- universal -> Claude/Codex conversion
- CLI smoke tests for multiple formats

## Releasing

Release automation is configured in [publish.yml](.github/workflows/publish.yml).
The one-time PyPI setup and release steps are documented in [releasing.md](docs/releasing.md).
