# ECC-N04-D03：资产生态 ingest 来源、签名与信任等级（草案）

> 状态：`draft`（条件立项阶段）。本文件在 **`ECC-N04-D01`**（`ecc_asset_registry_v1` 元数据字段）与 **`ECC-N04-D02`**（sanitizer 危险面隔离）之上，定义 **provenance / signature / trust** 的语义边界与 **与 sanitizer 决策的合流口径**，供后续 import/install 与人工 review 流程对齐。

## 1. 目标与边界

### 1.1 目标

- 统一 **来源（provenance）**、**完整性（integrity）**、**签名（signature）**、**信任等级（trust level）** 的可解释语义，避免与 `ecc_asset_registry_v1` 中已有字段重复定义却口径不一致。
- 给出 **“何时允许从 metadata-only 进入更高级别动作”** 的门禁组合：**sanitizer 结论** + **trust 下限** + **（未来）验签结果**。
- 输出可机读 **`ecc_ingest_provenance_trust_v1`** 草案，用于评审与后续 CLI/API 对齐。

### 1.2 本轮不做

- 不实现真实 **GPG / Sigstore / TUF** 验签流水线；仅定义 `signature.scheme` 枚举与 `verified` 语义占位。
- 不开放 **自动执行** 外部资产中的 hook/script；执行仍默认遵循 **`ECC-N04-D02`** 的 `deny-exec` 与 `hook_runtime` 门控。
- 不做在线市场拉取、不做社区运营评分系统。

## 2. 与 D01 / D02 的关系

| 输入 | 角色 |
|------|------|
| `ecc_asset_registry_v1.assets[]` | 单资产 **事实字段**：`source`、`license`、`signature`、`integrity`、`trust` |
| `ecc_ingest_sanitizer_policy_v1` | **内容风险** 预检：`decision` ∈ `reject` / `review` / `allow_metadata_only` |
| **`ecc_ingest_provenance_trust_v1`（本项）** | **信任与来源策略**：在 sanitizer 通过后，解释是否仍须人工确认、以及未来验签通过后可解锁哪些能力 |

**合流规则（v1 草案）**：

1. 若 sanitizer `decision == reject` → **整体 `reject`**，不信任字段不参与放行。
2. 若 sanitizer `decision == review` → **整体 `review`**，即使 `trust.level` 较高也须人工。
3. 若 sanitizer `decision == allow_metadata_only` → 读取本策略的 **trust gate**：低于 `reviewed` 的默认仍输出 **`review`**（保守），除非显式关闭（未来配置项，本轮不实现）。

## 3. Provenance（来源）

最小可接受 **来源声明**（与 registry 中 `source` 对齐）：

- `kind`：`git` | `http` | `file` | `unknown`（`unknown` 不得高于 `trust.level == unknown` 的自动策略）。
- `origin`：可解析 URI 或本地路径说明。
- `retrieved_at`：ISO8601，允许为空但须在 UI/报告中标为 **未证明时效**。

**来源强度（仅文档分级，非代码枚举）**：`unknown` < `file` < `http` < `git`（带 commit/tag 更佳，字段可放在扩展对象，本轮不强制 schema）。

## 4. Integrity（完整性）

与 `ecc_asset_registry_v1.assets[].integrity` 对齐：

- 推荐 **`sha256`** + `hash_value`；缺失时视为 **完整性未声明**，不得进入任何“可执行解锁”路径（未来定义）。

## 5. Signature（签名）

与 registry 中 `signature` 对齐：

- `scheme`：`none` | `gpg` | `sigstore` | `custom`（`custom` 须配 out-of-band 说明，本轮不机读解析）。
- `verified`：布尔；**本轮不自动验真**，仅允许人工或外部流水线写入 `true`。
- `key_id`：可选；用于审计展示。

## 6. Trust level（信任等级）

与 `ecc_asset_registry_v1.assets[].trust.level` 建议取值对齐（字符串枚举，可扩展）：

| `level` | 含义（产品语义） | v1 默认自动策略 |
|---------|------------------|-----------------|
| `unknown` | 未声明或无法归类 | 仅 `metadata`；**禁止**自动执行建议 |
| `community` | 社区来源，未审计 | 仅 `metadata`；**禁止**自动执行建议 |
| `reviewed` | 维护者已人工审阅记录 | 允许进入 **“可安装待人工确认执行”** 类流程的文档描述（仍非自动执行） |
| `publisher_verified` | 发布方 + 验签通过（未来） | 预留与 `signature.verified` 联动；**本轮仍不自动执行** |

## 7. 机读输出：`ecc_ingest_provenance_trust_v1`

见 `docs/schema/ecc_ingest_provenance_trust_v1.snapshot.json`。顶层建议字段：

- `schema_version`：固定 `ecc_ingest_provenance_trust_v1`
- `policy_status`：`draft`
- `trust_levels[]`：等级定义与 `allows_auto_execute`（v1 恒为 `false`）
- `signature_schemes[]`：支持的 scheme 列表
- `provenance_requirements`：最小/推荐元数据字段路径
- `gates[]`：逻辑门（sanitizer、trust、future_verification）
- `sample_evaluation`：示例合流结果

## 8. 验收口径（D03）

- 有独立 provenance/trust 策略文档（本文件）与英文伴随文档。
- 有机读快照样例 **`ecc_ingest_provenance_trust_v1.snapshot.json`**。
- `ecc_asset_registry_v1.snapshot.json` 的 `boundaries.provenance_policy_included` 置为 `true`，`next_steps` 指向执行链之外的下一里程碑说明。
- ROADMAP / TODOS / CHANGELOG / schema README 与本结论一致。

## 9. 后续里程碑（不在 D03）

- import/install 命令链与 **执行链** 门禁联调。
- 可选：与 `feedback bundle` / `export` 产物共享同一脱敏与路径策略（见 `CC-N02-D04`）。
