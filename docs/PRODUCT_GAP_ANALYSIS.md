# Product gap analysis (English companion)

> **English** summary. Canonical Chinese narrative: [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md).

## Current judgment

As of **2026-04-26**, two statements are both true:

1. **The previously tracked internal roadmap / backlog wave is effectively complete** for the items marked `Done` in [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10 (including the large Hermes tranche `HM-N05`–`HM-N10` and ingest policy drafts through **`ECC-N04-D03`**).
2. **CAI Agent is still not fully aligned** with the moving public surfaces of `claude-code`, `hermes-agent`, and `everything-claude-code`.

The remaining gap is mostly **product shells** (install/repair, profile home, API manageability, writable dashboard, plugin/home sync, asset packs) rather than “CLI cannot run”.

## Three upstream lines (short)

Use the Chinese source for the full table. At a high level:

- **Claude Code**: strong CLI/TUI core; weaker first-run install/repair and marketplace-style sync narratives.
- **Hermes Agent**: strong platform story; we shipped a large gateway/voice/memory/tool/runtime contract batch; remaining gaps include **second-wave platforms**, **OpenAPI/route expansion**, **writable dashboard depth**, and **isolated profile homes**.
- **Everything Claude Code**: strong asset methodology; remaining gaps are **home sync / pack lifecycle / ingest execution wiring** after the **`ECC-N04-D01`–`D03` document + snapshot** baseline.

## Next-wave alignment areas (from the Chinese source)

The Chinese document now tracks a fuller grouped backlog:

- **`MODEL-P0`**: completed; maintenance only.
- **`CC-N*`**: install/repair, feedback + redaction/export policy, plugin/home sync, richer session UX.
- **`HM-N*`**: `HM-N01` profile home; `HM-N03`/`HM-N04` API+dashboard; **`HM-N05`–`HM-N10` delivered** (gateway expansion batch, voice, memory registry, tool gateway); `HM-N06` second-wave platforms (Explore); `HM-N11` cloud runtime (Conditional).
- **`ECC-N*`**: `ECC-N01`/`ECC-N02` sync and pack lifecycle; `ECC-N03` cross-harness doctor/diff; **`ECC-N04` policy drafts D01–D03 done**, next is import/install execution chains tied to packs.
- **`*-Dxx`**: atomic tasks for sprint breakdown — see unified backlog [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md).

## Priority table (mirrors Chinese §4)

| Group | Top items | Notes |
|-------|-----------|--------|
| `MODEL-P0` | Completed | Model gateway, capabilities, health, routing explain, onboarding — see archive + roadmap. |
| `P0` external entrypoints | `CC-N01`, `HM-N01` | Install/repair and isolated profile homes. **`CC-N02` feedback line is `Done`** (bundle/export redaction landed in `CC-N02-D04`). |
| `P1` product shells | `CC-N03`, `CC-N04`, `HM-N03`, `HM-N04`, `ECC-N01`, `ECC-N03` | Dashboard, plugin/home sync, session UX, API manageability. **`HM-N05`/`HM-N07` gateway expansion + federation are already `Done`** — do not keep re-scheduling them as P0. |
| `P2` differentiation | `ECC-N02`, `HM-N06` | Asset pack lifecycle + second-wave gateway exploration. **`HM-N08`–`HM-N10` main paths are shipped**; **`ECC-N04-D01`–`D03` policy drafts are shipped`** — next work is **execution/import wiring**, not re-authoring the same policy docs. |
| `P3` conditional / Explore | `CC-N05`, `CC-N07`, `HM-N11`, `ECC-N05` | Desktop GUI, remote/cloud surfaces, real cloud runtimes, operator console — default off without authorization. |

## Explicit non-goals (this product cycle)

- Re-implementing native WebSearch / Notebook (stay **MCP-first**).
- Default cloud execution backends (**local/docker/ssh** remain default; cloud stays **Conditional**).
- Chasing every Hermes gateway platform at once (**HM-N06** is Explore / phased).

## Maintenance

- Keep this file aligned with [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) whenever priorities or “already shipped” posture changes.
- Execution detail: [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md); test migration note and finalize records: [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md).
- Release checklist cross-links: [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md), [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md).
