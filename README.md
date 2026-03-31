# plugin-crosswalk

`plugin-crosswalk` converts Claude-style plugin repos into more portable
artifacts:

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

Generate everything from the current directory:

```bash
plugin-crosswalk convert
```

Convert a specific Claude subplugin:

```bash
plugin-crosswalk convert --root /path/to/plugin --plugin app-development
```

Generate only universal skills:

```bash
plugin-crosswalk convert --skip-codex
```

Write without cleaning the existing output directory first:

```bash
plugin-crosswalk convert --no-clean
```

## Output layout

```text
dist/cross-provider/
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
- Codex package generation
- universal skill catalog generation
- CLI smoke tests
