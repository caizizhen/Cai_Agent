# Plugin surface machine-readable compatibility matrix (`plugin_compat_matrix_v1`)

> Chinese version: [PLUGIN_COMPAT_MATRIX.zh-CN.md](PLUGIN_COMPAT_MATRIX.zh-CN.md)

This page describes how **Cursor**, **OpenAI Codex CLI**, and **OpenCode** relate to the six extension directories in a CAI repo (`skills`, `commands`, `agents`, `hooks`, `rules`, `mcp-configs`). It matches the capability table in [CROSS_HARNESS_COMPATIBILITY.md](CROSS_HARNESS_COMPATIBILITY.md) and is materialized as JSON from **`build_plugin_compat_matrix()`** with `schema_version`: **`plugin_compat_matrix_v1`**.

## Consumption paths

| Scenario | Command / field |
|----------|-----------------|
| Standalone JSON | `cai-agent plugins --json --with-compat-matrix` (adds **`compat_matrix`** on top of `plugins_surface_v1`) |
| Doctor bundle | `cai-agent doctor --json` → **`plugins`** (`doctor_plugins_bundle_v1`): includes **`surface`** and **`compat_matrix`** |
| JSON Schema | `cai-agent/src/cai_agent/schemas/plugin_compat_matrix_v1.schema.json` |

## Status values

- **`supported`**: The target harness has a first-class or equivalent entry point for that asset class.
- **`partial`**: Requires export / adaptation or a format subset.
- **`absent`**: No equivalent on the target side; degrade the workflow (for example replace hooks with `quality-gate` wrappers).

## Matrix summary (aligned with code)

See `plugins.compat_matrix.components_vs_targets[]` and `targets[]` inside `doctor --json`. When you change behavior, keep these in sync:

1. `cai_agent.plugin_registry.build_plugin_compat_matrix`
2. This page and the **CROSS_HARNESS** table
3. `schemas/plugin_compat_matrix_v1.schema.json`

## Skills roadmap (G3 split)

- **Current focus**: In-repo `skills/` plus **`skills hub`** (`manifest` / `suggest` / `install` / `serve`) and **`export --target`**; see [PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md) §二 and [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md) (Chinese) for product decisions.
- **Large community skill corpora**: Prefer MCP / external packages over time; does not block core releases (consistent with [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) L3).
