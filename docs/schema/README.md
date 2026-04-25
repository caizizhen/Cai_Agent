# JSON Schema Index

> English companion summary. Chinese canonical source: [`README.zh-CN.md`](README.zh-CN.md).

This directory documents machine-readable `cai-agent` outputs: command `--json` payloads, dedicated JSONL files, `schema_version` conventions, and exit-code behavior.

Use [`README.zh-CN.md`](README.zh-CN.md) for the complete schema catalog. Keep this companion short and update it when the schema index changes shape, when new schema groups are added, or when English entrypoints need a stable schema link.

## Model gateway (MODEL-P0) JSON Schema files

Machine-readable drafts live under [`cai-agent/src/cai_agent/schemas/`](../../cai-agent/src/cai_agent/schemas/) (relative to this `docs/schema/` page). Key contracts:

- **`model_response_v1.schema.json`** — normalized `ModelResponse` envelope (`chat_response`, API chat completions internals)
- **`model_capabilities_v1.schema.json`** / **`model_capabilities_list_v1.schema.json`** — non-secret capability snapshots
- **`model_onboarding_flow_v1.schema.json`** — `cai-agent models onboarding --json` command chain
- **`provider_registry_v1.schema.json`** — `models list --providers --json` extra presets + `capabilities_hint`
- **`models_routing_test_v1.schema.json`** — `models routing-test --json` including explain-only fallback candidates
- **`model_fallback_candidates_v1.schema.json`** — nested **`fallback_candidates`** object (same contract as in routing-test)
- **`routing_explain_v1.schema.json`** — nested **`explain`** object (same contract as in routing-test)
- **`doctor_model_gateway_v1.schema.json`** — nested **`doctor_v1.model_gateway`** object (capabilities list, health enum, runbook path, recommended CLI flow)
- **`api_models_capabilities_v1.schema.json`** — **`GET /v1/models/capabilities`** (wraps **`model_capabilities_list_v1`**)
- **`api_openai_models_v1.schema.json`** — OpenAI **`GET /v1/models`**
- **`api_openai_chat_completion_v1.schema.json`** / **`api_openai_chat_completion_chunk_v1.schema.json`** — OpenAI **`POST /v1/chat/completions`** (non-stream + SSE chunk)

Full tables and exit semantics remain in the Chinese source [`README.zh-CN.md`](README.zh-CN.md).
