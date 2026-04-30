# Context compaction N04-N07 integration QA - 2026-04-30

## Scope

- `CTX-COMPACT-N04`: LLM summary retention gate with heuristic fallback.
- `CTX-COMPACT-N05`: JSON Schema files and fixture checks for summary/eval/retention payloads.
- `CTX-COMPACT-N06`: repeated compaction merges existing `context_summary_v1` evidence.
- `CTX-COMPACT-N07`: tool-aware evidence extraction for tests, traceback, git diff, search, read, and command outputs.

## Passed

```powershell
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' -m compileall -q cai-agent/src/cai_agent/context_compaction.py cai-agent/src/cai_agent/graph.py cai-agent/src/cai_agent/tui.py cai-agent/src/cai_agent/__main__.py
```

Result: PASS.

```powershell
$env:TMP='D:\gitrepo\Cai_Agent\.tmp\pytest-ctx-final'
$env:TEMP='D:\gitrepo\Cai_Agent\.tmp\pytest-ctx-final'
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp .tmp\pytest-ctx-final\basetemp cai-agent/tests/test_context_compaction.py cai-agent/tests/test_graph_context_compaction.py cai-agent/tests/test_sessions_compact_eval_cli.py cai-agent/tests/test_cost_aggregate.py::test_compact_policy_explain_v1
```

Result: `22 passed in 0.50s`.

## Environment Blocked

```powershell
$env:TMP='D:\gitrepo\Cai_Agent\.tmp\smoke-final'
$env:TEMP='D:\gitrepo\Cai_Agent\.tmp\smoke-final'
$env:PYTHONPATH='D:\gitrepo\Cai_Agent\cai-agent\src'
& 'D:\gitrepo\Cai_Agent\.uv-env-main\Scripts\python.exe' scripts\smoke_new_features.py
```

Result: blocked before feature assertions by Windows ACL on the Python-created temporary directory:

```text
PermissionError: [Errno 13] Permission denied: 'D:\gitrepo\Cai_Agent\.tmp\smoke-final\cai-smoke-wf-...\smoke-workflow.json'
PermissionError: [WinError 5] 拒绝访问。: 'D:\gitrepo\Cai_Agent\.tmp\smoke-final\cai-smoke-wf-...'
```

## Conclusion

The context compaction N04-N07 integration path passed focused compile and pytest gates. `scripts/smoke_new_features.py` is not claimed as passing in this Windows workspace because Python-created temporary directories are denied by local ACL policy before smoke assertions run.
