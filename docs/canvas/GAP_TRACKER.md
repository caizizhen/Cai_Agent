# Canvas gap tracker (aligned with the current roadmap)

This file is no longer a separate planning source. It only mirrors the active backlog in [`../ROADMAP_EXECUTION.zh-CN.md`](../ROADMAP_EXECUTION.zh-CN.md) so the old canvas rows do not drift away from the current three-repo product plan.

## 1. Mapping: old canvas rows -> current roadmap IDs

| Old row | Current roadmap ID | Meaning now |
|----|----|----|
| `A1` / `A3` / `E1` | `HM-05` | Memory providers, user model, recall evaluation, memory policy gates |
| `B1` / `B2` / `B3` / `B4` | `HM-03` | Discord, Slack, gateway ops, gateway perf/productization |
| `D1` / `D2` | `HM-04` | Ops dashboard and dynamic read-only operations UI |
| `F1` / `F2` | `ECC-02` | Cost dashboard, model routing, compact triggers |
| `G3` | `ECC-01` | Rules / skills / hooks assetization and install flow |
| `G4` / `I1` / `I2` | `REL-01` | Feedback loop, release checklist, semantic changelog |
| `H1` | `HM-06` | Runtime backends productization |
| `J1` / `J2` | `HM-07` or `OOS` | Voice / native WebSearch-Notebook style boundaries |

## 2. Active tracker

Status vocabulary:

- `Done`: already closed in the current doc consolidation / roadmap pass
- `Ready`: can be opened as a development issue now
- `Design`: needs a schema or contract decision first
- `Explore`: research or boundary-setting only, not default delivery this cycle

| ID | Status | Suggested next issue | Pointer |
|----|--------|----------------------|---------|
| `DOC-01` | `Done` | Keep entry docs and canonical set stable | `ROADMAP_EXECUTION` §10 |
| `REL-01` | `Ready` | `REL-01b` feedback / doctor / release summary unification | `ROADMAP_EXECUTION` §10 |
| `CC-01` | `Done` | **`CC-01b` Done** — `/mcp-presets` + task board/help/status quickstart + `mcp-check` epilog | `ROADMAP_EXECUTION` §10 |
| `CC-02` | `Done` | **`CC-02b` Done** — `feedback bug` + `feedback_bug_report_v1` | `ROADMAP_EXECUTION` §10 |
| `CC-03` | `Done` | **`CC-03a`/`CC-03b` Done**（`tui_session_strip` + RFC **CC-03b**） | `ROADMAP_EXECUTION` §10 |
| `HM-01` | `Done` | **`HM-01a`/`HM-01b` Done** — profile contract + management CLI/fixture/smoke | `ROADMAP_EXECUTION` §10 |
| `HM-02` | `Done` | **`HM-02a`/`HM-02b` Done**（RFC + **`api serve`**） | `ROADMAP_EXECUTION` §10 |
| `HM-03` | `Done` | **`HM-03a` / `HM-03b` Done**: Discord + Slack production path closed for current cycle | `ROADMAP_EXECUTION` §10 |
| `HM-04` | `Done` | **`HM-04a`/`HM-04b` Done**: shared gateway summary + dynamic read-only dashboard | `ROADMAP_EXECUTION` §10 |
| `HM-05` | `Done` | **`HM-05a`/`HM-05b`/`HM-05c` Done**（recall 评估、doctor/release policy） | `ROADMAP_EXECUTION` §10 |
| `HM-06` | `Explore` | `HM-06a` backend productization evaluation | `ROADMAP_EXECUTION` §10 |
| `HM-07` | `Explore` | `HM-07a` voice boundary evaluation | `ROADMAP_EXECUTION` §10 |
| `ECC-01` | `Done` | **`ECC-01a`/`ECC-01b` Done**（`ecc` CLI + 安装/导出/共享文档） | `ROADMAP_EXECUTION` §10 |
| `ECC-02` | `Done` | **`ECC-02a`/`ECC-02b` Done**（routing-test / cost report + compact explain） | `ROADMAP_EXECUTION` §10 |
| `ECC-03` | `Explore` | `ECC-03a` plugin/version governance design | `ROADMAP_EXECUTION` §10 |

## 3. Usage rule

When a roadmap item changes status:

1. Update [`../ROADMAP_EXECUTION.zh-CN.md`](../ROADMAP_EXECUTION.zh-CN.md) first.
2. Mirror the status here.
3. If an old canvas row becomes irrelevant, map it to `OOS` instead of inventing a new parallel bucket.
