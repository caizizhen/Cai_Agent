# Product Gap Analysis

> English companion summary. Chinese canonical source: [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md).

## Current judgment

As of 2026-04-25, two statements are both true:

- The previously tracked internal roadmap / backlog wave is effectively complete.
- CAI Agent is still **not fully aligned** with the current public surfaces of `claude-code`, `hermes-agent`, and `everything-claude-code`.

The current gap is no longer about core CLI viability. It is mostly about **product surfaces around the core agent**.

## Main next-wave alignment areas

The Chinese source now treats the remaining gap as a fuller grouped backlog instead of only a short future queue:

- `MODEL-P0`: completed as the model integration foundation, covering a unified model gateway contract, model capability metadata, health/chat-smoke checks, normalized response envelopes, routing explainability, explain-only fallback candidates, and an onboarding command-chain runbook
- `CC-N*`: unfinished Claude Code-facing surfaces such as install/repair, feedback flow, plugin/home sync, and richer session UX
- `HM-N*`: unfinished Hermes-facing surfaces such as isolated profile homes, API server management/OpenAPI follow-up, writable dashboard, more gateway platforms, voice, external memory providers, and tool-gateway-like integrations; the minimal OpenAI-compatible `/v1/models` and `/v1/chat/completions` path plus the MODEL-P0 model foundation are now covered in the Chinese source
- `ECC-N*`: unfinished ECC-facing surfaces such as local catalog/sync, asset pack lifecycle, cross-harness doctor/diff, and broader asset-registry ingestion
- `*-Dxx`: atomic implementation tasks that developers and testers can use directly for issue breakdown and sprint planning

Use the Chinese source for the full rationale, status, priorities, and boundaries.

## Maintenance

- Keep this summary aligned with the Chinese source.
- Use [DEVELOPER_TODOS.zh-CN.md](DEVELOPER_TODOS.zh-CN.md) and [TEST_TODOS.zh-CN.md](TEST_TODOS.zh-CN.md) for execution detail.
- Do not add an independent long-form planning matrix here.
