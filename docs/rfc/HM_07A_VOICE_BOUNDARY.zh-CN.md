# HM-07a：Voice 能力边界与 OOS 评估（结论文档）

## 1. 能力分解

| 子能力 | 输入 | 输出 | 依赖 |
|--------|------|------|------|
| **STT** | 音频流 / 文件 | 文本 | 云端 ASR 或本地模型 |
| **TTS** | 文本 | 音频 | 云端合成或本地引擎 |
| **双工会话** | 低延迟双向流 | 打断、回声消除 | 设备与网络 QoS |
| **电话 PSTN** | 电话号码 | 电信网关 | 运营商合规 |

## 2. 默认产品结论：**OOS（不默认交付）**

- **理由**：密钥与隐私（语音生物特征）、实时链路 SLA、多端 SDK 绑定、以及与 **Claude / 多模型** 路由的统一成本过高。
- **替代路径**：通过 **MCP** 接入用户自选的 STT/TTS 服务；或外部客户端完成语音后，以 **文本** 进入 **`cai-agent run`**。

## 3. 若未来条件立项的门槛

- 明确 **数据驻留**与**日志不落敏感音频**默认策略。
- 与 **gateway** 场景解耦：语音不宜与 Telegram/Slack _bot 生命周期强行绑在同一进程。

## 4. 验收

- **`PARITY_MATRIX`** / **`PRODUCT_GAP`** 可将 Voice 标为 **OOS + MCP** 而不必保留模糊「Next」。

## 5. HM-N08-D04 可用边界（当前实现）

- **已交付（可用）**
  - `voice_provider_contract_v1`：`doctor --json` 与 `cai-agent voice config --json` 可输出 provider/STT/TTS/health 机读状态。
  - `cai-agent voice check --json`：返回 `voice_check_v1`，并以退出码 `0/2` 表示已配置/未配置。
  - `cai-agent gateway telegram voice-reply --json`：支持最小语音回发闭环（依赖 Telegram `voice_file_id`）。
- **当前不做（OOS）**
  - 不做内置实时 STT/TTS 引擎（无实时双工、无流式打断）。
  - 不做音频文件落盘与长期存储（默认不处理敏感音频资产）。
  - 不做 PSTN/电话网关、会议室设备级语音链路。
  - 不做跨平台统一语音 SDK（Telegram 以外平台后续再评估）。

## 6. 成本与风险提示（运营侧）

- **成本面**
  - 若启用外部语音 provider，成本主要来自 STT/TTS 按时长或字符计费；本仓当前只暴露配置与健康，不内置预算控制。
  - Telegram `voice-reply` 使用 `voice_file_id` 回发已存在语音资源，不做本地合成，因此不引入额外 CPU/GPU 推理成本。
- **安全与合规**
  - API Key 仅做“是否存在”检查，不在 JSON 载荷输出明文。
  - 语音能力默认保持“显式启用”策略：需同时配置 provider/endpoint/api_key 才算 configured。
- **上线建议**
  - 先在测试群验证 `voice check` 与 `gateway telegram voice-reply`，再进入生产 Bot。
  - 建议将语音 provider 成本上限放在外部平台（provider 侧）或网关层流量控制，不依赖当前 CLI 做预算兜底。
