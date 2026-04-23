# Canvas gap tracker (Tier 2)

Cross-links Tier 0/Tier 1 deliveries vs. canvas rows. Update as features land.

| ID | Theme | Status / pointer |
|----|-------|-------------------|
| A1 | Honcho engine | `user_model_store.py`, `build_memory_user_model_overview_v3`, `memory user-model query/learn`, `docs/MEMORY_STRATEGY.zh-CN.md` |
| A3 | Recall accuracy | `recall --evaluate`, `negative_queries_top`, `recall_evaluation_v1` + `recall_evaluation_sample` |
| E1 | Memory TTL / policy | `[memory.policy]`, `doctor --json` → `memory_policy`, `release-ga --with-memory-policy`, `memory entries fix` |
| B1 | Discord Slash | `gateway/discord-session-map.json` health in `doctor`; full `interaction_create` router still gateway backlog |
| B2 | Slack Slash | `slack-session-map.json` + Block Kit backlog; see gateway docs when added |
| B3 | Gateway ops | `doctor` gateway maps; unified `/v1/ops/gateway` backlog |
| B4 | Gateway perf | `scripts/perf_ga_gate.py`, `scripts/perf_recall_bench.py` — extend for 500-msg scenario in ops runbook |
| D1 / D2 | Ops UI | Canvas React backlog; CLI `board` / `ops` payloads remain anchors |
| F1 | Cost dashboard | `cost report --json`, `cost_by_profile_v1`, flags `--by-tenant`, `--per-day`, `models route-wizard` |
| F2 | Compact triggers | `graph.py`: `compact:research_done`, `compact:pre_retry`, milestone + iteration hooks |
| G3 | Skills hub | `skills hub install --from/--manifest`, `skills hub list-remote`, `.cai/skills-registry-mirror.jsonl` |
| G4 | Feedback | `feedback submit/list/export`, `doctor --json.feedback`, `.cai/feedback.jsonl` |
| H1 | Cloud runtime | `RUNTIME_BACKENDS.md` / `.zh-CN.md`, `[runtime]`, Modal/Daytona/Singularity stubs + singularity exec MVP |
| I1 | T7 checklist | `scripts/t7_checklist_backfill.py`, `.github/workflows/t7-checklist-example.yml` |
| I2 | Changelog semantic | `release-changelog --semantic` → `changelog_semantic_v1` |
| J1 / J2 | OOS | See `docs/canvas/OOS_J1_J2.md` |
