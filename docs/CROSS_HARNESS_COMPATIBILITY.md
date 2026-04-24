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

## Repo-root asset layout (ECC-01a)

Default resolution order (shared with `cai_agent.ecc_layout` and `doctor`):

| Asset | Paths | Notes |
|-------|-------|-------|
| rules | `rules/common/*.md`, `rules/python/*.md` | Injected during `plan` |
| skills | `skills/*.md` (except `README.md`) | Skill binding / hub |
| hooks | `hooks/hooks.json` then `.cai/hooks/hooks.json` | First existing file wins |

**Scaffold**: `cai-agent ecc -w <root> scaffold` creates minimal README / sample skill / empty `hooks.json` without overwriting existing files. **Machine-readable index**: `cai-agent ecc -w <root> layout --json` → **`ecc_asset_layout_v1`** (pass `-w` before the subcommand).

## Install / export / share flow (ECC-01b)

Single story so teams know where assets land and how to hand off a repo:

1. **Bootstrap**: `cai-agent init` (or `init --preset starter`) → root `cai-agent.toml`; first sanity check `cai-agent doctor`.
2. **ECC assets**: `cai-agent ecc -w . layout --json` → `ecc_asset_layout_v1`; if empty, `ecc scaffold` adds minimal `skills/` + `hooks/hooks.json` samples (no overwrites).
3. **Export**: `cai-agent export --target cursor|codex|opencode` → `.cursor/`, `.codex/`, `.opencode/`; use `export --ecc-diff` (`export_ecc_dir_diff_v1`) for a no-write diff report before PRs.
4. **Share**: Prefer a **Git repo** + **secrets-free TOML** (`api_key_env`); peers verify `doctor --json` → `installation_guidance` + `plugins.compat_matrix`.
5. **Machine-readable matrix**: `plugins --json --with-compat-matrix` matches `doctor --json.plugins.compat_matrix`.

## Acceptance (P2)

- One repo can export at least two harness configurations.
- Roughly 80% of core workflows (plan / run / review / verify) have an executable substitute on the target harness.
- Unsupported capabilities surface explicit hints and fallback paths.
