# 运行后端选型（H1-RT）

> CLI：`cai-agent runtime list`、`cai-agent runtime test --backend local --json`  
> 配置：`[runtime]` / `[runtime.docker]` 等见 `cai-agent.example.toml`。

| 后端 | 隔离度 | 冷启动 | 成本直觉 | 适用 |
|------|--------|--------|----------|------|
| **local** | 低（本机进程） | 无 | 低 | 默认开发、CI 单测 |
| **docker** | 中高（容器） | 中 | 中 | 与生产镜像对齐的集成环境 |
| **ssh** | 依赖远端策略 | 低 | 低–中 | 已有 VM / 跳板机 |
| **modal** | 高（serverless） | 高–中 | 按量 | 弹性算力、长任务 offload |
| **daytona** | 高 | 中 | 中 | 云端 dev workspace |
| **singularity** | 高（HPC） | 中 | 低–中 | 集群 / 共享文件系统 |

当前仓库状态：

- **local**：已实现（`subprocess`，`run_command` 默认路径）。
- **docker / ssh**：`docker exec` / OpenSSH；支持 `[runtime.docker]` 的 `exec_options` / `cpus` / `memory`，`[runtime.ssh]` 的 `strict_host_key_checking` / `known_hosts_path` / `connect_timeout_sec`。
- **singularity**：若本机有 `singularity` 或 `apptainer` 且配置了 `sif_path`，可走 `singularity exec`（含 `bind_paths`）。
- **modal / daytona**：Modal 仍为 SDK 桩；Daytona 检测 CLI + `workspace` 配置，稳定 `exec` 子命令待版本对齐（见 `daytona_exec_not_implemented`）。

### `run_command` 派发

非 `local` 时，`tools.tool_run_command` 通过 `get_runtime_backend` 调用 `RuntimeBackend.exec`；`CAI_RUNTIME_BACKEND` 可覆盖 TOML 的 `runtime.backend`。LangGraph 进度事件里对 `run_command` 附带 `runtime_backend` 字段。

### 诊断

`cai-agent doctor --json` 含 `runtime: { schema_version: doctor_runtime_v1, … }`。
