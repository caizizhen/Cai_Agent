# Browser full regression - 2026-04-29

- Scope: browser MCP/provider chain plus full `cai-agent/tests` regression.
- Command: `python -m pytest -q -p no:cacheprovider --basetemp .tmp/pytest-full-basetemp cai-agent/tests`
- Smoke command: `python scripts/smoke_new_features.py`
- Environment note: Windows sandbox used repository-local `.tmp/pytest-full-basetemp`; the test process normalized `0o700` temp directory creation to `0o777` to avoid system Temp ACL failures.
- Result: PASS, `897 passed, 3 subtests passed in 76.23s`.
- Smoke result: PASS, `NEW_FEATURE_CHECKS_OK`.
- Follow-up fix included: `scripts/perf_recall_bench.py` now uses a repository-local `.tmp/perf-recall-bench-*` workspace so subprocess benchmark tests do not depend on system Temp ACLs.
