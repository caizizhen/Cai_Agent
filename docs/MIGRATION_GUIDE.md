# Migrating to cai-agent 0.6.x from 0.5.x

This guide summarizes **breaking changes** and practical upgrade steps. The canonical per-version list remains **[`CHANGELOG.md`](../CHANGELOG.md)** (English) and **[`CHANGELOG.zh-CN.md`](../CHANGELOG.zh-CN.md)** (Chinese).

## 1. Environment

- **Python**: `3.11+` (see `cai-agent/pyproject.toml` **`requires-python`**).
- **Install**: from repo root, `cd cai-agent && pip install -e .` (or install the wheel for your release). Confirm with:

```bash
python -m cai_agent --version
```

## 2. Breaking changes that affect automation

### 2.1 Versioned JSON envelopes (`--json`)

Many commands now print a **single JSON object** with **`schema_version`** and typed fields. Pipelines that assumed **bare arrays** or undocumented shapes must be updated.

| Command / area | Old (0.5.x style) | New (0.6.x) |
|----------------|-------------------|-------------|
| `sessions --json` | Bare array of sessions | **`sessions_list_v1`** with **`sessions`** array |
| `schedule list --json` | Bare array of jobs | **`schedule_list_v1`** with **`jobs`** |
| `commands --json` / `agents --json` | Bare string arrays | **`commands_list_v1`** / **`agents_list_v1`** |
| `models fetch --json` | Bare `models` array | **`models_fetch_v1`** wrapper; read **`models`** |
| `memory list|search|instincts --json` | Bare arrays | **`memory_list_v1`**, **`memory_search_v1`**, **`memory_instincts_list_v1`** |

**Action**: After upgrade, grep your scripts for `jq` / `python -c` parsers and align with **[`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md)** (schema index, S1-02 / S1-03).

### 2.2 Exit codes (S1-03)

- **`cai-agent init`**: failure paths (**`config_exists`**, **`template_read_failed`**, **`mkdir_failed`**) use **exit `2`** (previously **`1`** in some paths).
- **`models ping`**: any non-OK model result defaults to **exit `2`** (previously **`1`**). **`--fail-on-any-error`** remains a **no-op alias** for compatibility.
- **Unhandled CLI command** (internal dispatch gap): **exit `2`** with one stderr line (previously **`1`**).

**Action**: In CI, treat **exit `2`** as “CLI reported failure” for these commands; keep **exit `130`** for Ctrl+C on `run` / `continue` where documented.

### 2.3 Schedule persistence and audit

- **`.cai-schedule.json`** tasks may include **`max_retries`**, **`retry_count`**, **`next_retry_at`**, **`depends_on`** (cycles rejected at add time).
- **`.cai-schedule-audit.jsonl`** lines use a **unified schema** (`schema_version`, `event`, …). See **[`docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md)**.

**Action**: If you parse audit files with ad-hoc parsers, migrate to the documented **`event`** set.

### 2.4 Recall JSON

- Zero-hit responses include **`no_hit_reason`** and **`schema_version` `1.3`**. Sorting supports **`--sort recent|density|combined`**.

## 3. Recommended upgrade checklist

1. Upgrade the package; run **`cai-agent doctor`** in a throwaway copy of a workspace.
2. Run your integration scripts once with **`--json`** and diff against saved golden files.
3. Update **`jq`/Python** paths to nested keys (e.g. **`.sessions[]`** instead of **`.[]`** for sessions list).
4. Re-run **`pytest`** (or your subset) if you vendor extensions that import `cai_agent` internals.
5. For Telegram / gateway: follow **`CHANGELOG`** 0.6.1–0.6.5 and **[`docs/qa/sprint6-gateway-telegram-testplan.md`](qa/sprint6-gateway-telegram-testplan.md)**.

## 4. New capabilities (optional adoption)

You do not have to adopt these immediately; they are additive CLI surfaces:

- **0.6.0**: `schedule stats`, workflow **`on_error`** / **`budget_max_tokens`**, recall doctor / bench, memory health & nudge-report, etc.
- **0.6.1–0.6.5**: `gateway platforms`, `skills hub manifest`, `ops dashboard`, Telegram **`gateway setup|serve-webhook|…`**, allowlist, **`continue-hint`**.
- **0.6.6–0.6.8**: **`CAI_METRICS_JSONL`**, **`observe report`**, **`insights --json --cross-domain`**, **`observe export`**.

## 5. Deprecations

- No fields were removed in 0.6.0 solely as “deprecated without replacement”; see **`CHANGELOG`** **Deprecations** under **0.6.0** for the small compatibility notes (e.g. **`models ping`** alias).
