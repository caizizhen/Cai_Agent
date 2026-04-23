# CAI Agent runtime backends (EN)

This document mirrors the Chinese guide [`RUNTIME_BACKENDS.zh-CN.md`](./RUNTIME_BACKENDS.zh-CN.md).

## Summary

| Backend | Isolation | Notes |
|--------|-----------|-------|
| `local` | Low (host `subprocess`) | Default; `run_command` uses argv list + `shell=False`. |
| `docker` | Medium–high | `docker exec` into a named container; optional `cpus` / `memory` / `exec_options`. |
| `ssh` | Depends on remote | OpenSSH client; `BatchMode=yes`, configurable `StrictHostKeyChecking` + `known_hosts`. |
| `modal` / `daytona` / `singularity` | Optional | Extras / local CLI; stubs or minimal bridges — see `describe()` via `doctor --json`. |

## Configuration

- TOML: `[runtime]`, `[runtime.docker]`, `[runtime.ssh]`, `[runtime.modal]`, `[runtime.daytona]`, `[runtime.singularity]`.
- Environment override: `CAI_RUNTIME_BACKEND` wins over `runtime.backend` when set to a non-empty value.

## `run_command` dispatch

When `[runtime].backend` is not `local`, `tool_run_command` serializes argv with POSIX `shlex.join` and runs it through `RuntimeBackend.exec` with `cwd` set to the resolved workspace path (ensure container bind-mounts align with host paths).

Graph progress events for `run_command` include `runtime_backend` (resolved registry name).

## Security

- Prefer non-root containers; use `exec_options` (e.g. `--user`) and image-level resource limits.
- For SSH, keep `strict_host_key_checking = true` and pin `known_hosts_path` in production.

## CLI

- `cai-agent runtime list --json`
- `cai-agent runtime test --backend local --json`
- `cai-agent doctor --json` → `runtime` block (`doctor_runtime_v1`)
