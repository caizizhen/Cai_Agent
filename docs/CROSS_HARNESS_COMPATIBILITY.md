# Cross-harness compatibility (Cursor / Codex / OpenCode / Claude-class)

> Chinese version: [CROSS_HARNESS_COMPATIBILITY.zh-CN.md](CROSS_HARNESS_COMPATIBILITY.zh-CN.md)

This document defines how Cai_Agent maps assets across multiple agent harnesses.

## Goals

- Reuse the same rules / skills / agent templates across harnesses where possible.
- Where a capability is missing, offer a **degraded substitute** instead of failing silently.

## Capability map (v1)

| Capability | Claude-class | Cursor | Codex | OpenCode | Cai_Agent approach |
|------------|--------------|--------|-------|----------|-------------------|
| rules | Native rules dir | Supported | Instruction files first | instructions | Keep `rules/` as the single source |
| skills | `skills/` | Shareable | Partially shared formats | Mappable | Unified markdown skill bodies |
| agents | `agents/*.md` | Supported | Role files | Supported | Unified templates + export adapters |
| hooks | Strong | Strong | Weak / none | Strong | Degrade to pre/post checks or `quality-gate` |
| mcp | Strong | Supported | Supported | Supported | Keep `mcp-configs/` as the unified config source |
| Command entry | Slash | Command palette | Instructions / config | Slash | Unified `commands/` plus CLI subcommands |

## Degradation strategies

1. **No hooks**: Map hook logic to `quality-gate` and thin CLI wrapper scripts.
2. **Skill format drift**: Treat plain markdown as the interchange format, then render for each target.
3. **Agent metadata drift**: Keep a minimal common set (`name` / `description` / `tools`); inject harness-specific fields only when needed.

## Minimal adapter implementation

- Discovery: `cai-agent plugins --json` (extension surface).
- Export: `cai-agent export --target <cursor|codex|opencode>`.
- Typical output roots: `.cursor/`, `.codex/`, `.opencode/`.

## Manifest (`cai-export-manifest.json`)

- **`schema`**: Fixed `export-v2` (export JSON shape generation).
- **`manifest_version`**: Semantic version (**2.1.0** today); bump when fields, `copied` semantics, or target directory contracts change.
- **`target`**: `cursor` | `codex` | `opencode`.

## Machine-readable matrix (CLI / doctor)

The same semantics as the table above are available as JSON: **`plugin_compat_matrix_v1`** via `cai-agent plugins --json --with-compat-matrix`, and as **`doctor --json` → `plugins.compat_matrix`**. Human maintenance notes: [PLUGIN_COMPAT_MATRIX.md](PLUGIN_COMPAT_MATRIX.md) / [PLUGIN_COMPAT_MATRIX.zh-CN.md](PLUGIN_COMPAT_MATRIX.zh-CN.md).

## Acceptance (P2)

- One repo can export at least two harness configurations.
- Roughly 80% of core workflows (plan / run / review / verify) have an executable substitute on the target harness.
- Unsupported capabilities surface explicit hints and fallback paths.
