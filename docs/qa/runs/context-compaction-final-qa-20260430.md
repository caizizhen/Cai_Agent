# Context compaction final QA - 2026-04-30

## Scope

- `CTX-COMPACT-N01`: heuristic `context_summary_v1` compaction, graph auto trigger, and TUI `/compress`.
- `CTX-COMPACT-N02`: `compact_mode = off | heuristic | llm`, LLM compaction prompt, fallback, and cost policy reporting.
- `CTX-COMPACT-N03`: `sessions --compact-eval --json` offline quality gate.
- Follow-up handoff plan: `docs/CONTEXT_COMPACTION_FUTURE_PLAN.zh-CN.md`.

## Passed

```powershell
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' -m compileall -q cai-agent/src/cai_agent/context_compaction.py cai-agent/src/cai_agent/graph.py cai-agent/src/cai_agent/tui.py cai-agent/src/cai_agent/__main__.py cai-agent/src/cai_agent/config.py cai-agent/src/cai_agent/cost_aggregate.py
```

Result: PASS.

```powershell
$env:TMP='D:\gitrepo\Cai_Agent\.tmp\pytest-context'
$env:TEMP='D:\gitrepo\Cai_Agent\.tmp\pytest-context'
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp .tmp\pytest-context\basetemp cai-agent/tests/test_context_compaction.py cai-agent/tests/test_graph_context_compaction.py cai-agent/tests/test_sessions_compact_eval_cli.py cai-agent/tests/test_cost_aggregate.py::test_compact_policy_explain_v1
```

Result: `14 passed in 0.39s`.

```powershell
git check-ignore -v .test-tmp/pytest .tmp/smoke/manual-write-check.txt
```

Result: `.test-tmp/` and `.tmp/` are ignored by `.gitignore`, including `.test-tmp/pytest`.

## Blocked Environment Checks

Full suite attempt:

```powershell
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp .tmp/pytest-full cai-agent/tests
```

Result: blocked in this Windows workspace. The run emitted broad failures/errors and then failed during pytest session cleanup with:

```text
PermissionError: [WinError 5] 拒绝访问。: 'D:\gitrepo\Cai_Agent\.tmp\pytest-full'
```

Smoke attempt with system temp:

```powershell
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' scripts/smoke_new_features.py
```

Result: blocked before feature assertions by temporary directory ACL:

```text
PermissionError: [Errno 13] Permission denied: 'C:\Users\win11\AppData\Local\Temp\cai-smoke-wf-...\smoke-workflow.json'
```

Smoke attempt with repo-local temp:

```powershell
$env:TMP='D:\gitrepo\Cai_Agent\.tmp\smoke'
$env:TEMP='D:\gitrepo\Cai_Agent\.tmp\smoke'
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' scripts/smoke_new_features.py
```

Result: still blocked before feature assertions by temp child directory ACL:

```text
PermissionError: [Errno 13] Permission denied: 'D:\gitrepo\Cai_Agent\.tmp\smoke\cai-smoke-wf-...\smoke-workflow.json'
```

Manual write to `.tmp\smoke\manual-write-check.txt` succeeded, while `icacls` against the Python-created smoke temp child directory returned `Access is denied`.

## Conclusion

The context compaction implementation and handoff docs passed focused compile/test gates. Full-suite and smoke validation are not claimed as passing because the current Windows environment blocks Python-created temporary directories. Future release QA should rerun the full suite and smoke on a clean runner or after fixing local temp ACL policy.
