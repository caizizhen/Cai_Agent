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

## RT-N01 验证矩阵

> 目标：Docker / SSH 后端继续保持产品化接口可测，同时 CI 默认不绑定真实外部环境。

| 层级 | 覆盖范围 | 默认入口 | 通过门槛 |
|---|---|---|---|
| mock / unit | local、docker、ssh backend 接口与命令拼装 | `python -m pytest -q cai-agent/tests/test_runtime_local.py cai-agent/tests/test_runtime_docker_mock.py cai-agent/tests/test_runtime_ssh_mock.py cai-agent/tests/test_runtime_tool_dispatch.py` | 不要求本机 Docker daemon 或真实 SSH 主机；只验证接口、describe、派发与安全字段 |
| doctor contract | `doctor_runtime_v1.describe` 中 backend、mode、image/container、ssh key/known_hosts/audit 等字段 | `python -m pytest -q cai-agent/tests/test_doctor_cli.py -k runtime`（或全量 doctor 窄测） | 字段稳定，未配置环境给出可解释状态而非硬失败 |
| opt-in real smoke | 真实 Docker image / SSH target | 手工设置环境后运行专门 smoke（后续可落到 `docs/qa/runs/`） | 只在操作者显式提供 daemon/host/凭据时执行；失败记录环境信息，不阻塞默认 CI |

### 真实 smoke 边界

- Docker：默认建议使用短生命周期 image 模式；需要显式 image、workdir 与 volume 映射，避免复用未知长跑容器。
- SSH：必须使用显式 host、user、key、known_hosts 与 timeout；审计默认不写命令明文。
- CI：默认只跑 mock / contract 层；真实 smoke 可作为发布前人工或受保护 runner 的附加证据。
