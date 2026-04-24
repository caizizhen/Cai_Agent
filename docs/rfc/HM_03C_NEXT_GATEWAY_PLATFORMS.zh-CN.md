# HM-03c：下一批 Gateway 平台评估（结论文档）

> 依赖：**`HM-03a`**（Discord）、**`HM-03b`**（Slack）已 MVP。本文给出 **优先级 / 边界 / 不做清单**，不承诺实现日期。

## 1. 评估维度

| 维度 | 说明 |
|------|------|
| **Webhook 模型** | 事件推送 vs 长轮询；是否与现有 **`gateway_lifecycle`** 模式可类比 |
| **身份与租户** | 团队 / 工作区 / 多租户映射是否可落到 **`.cai/gateway/*-session-map.json`** 同类结构 |
| **合规与账号** | 是否依赖封闭企业合同、地区政策、或仅个人开发者可接入 |
| **Hermes 对齐价值** | 是否属于 Hermes 产品面常见「第二落点」 |

## 2. 候选平台（摘要）

| 平台 | 优先级建议 | 结论（本仓库口径） |
|------|------------|---------------------|
| **Microsoft Teams** | **P1（企业）** | Bot Framework + Graph 能力完整，与 Slack 同属「工作协作」象限；**下一批最值得立项**（需独立设计：应用注册、租户 ID、消息卡片与 slash 对齐） |
| **Matrix（Element 等）** | **P2（OSS）** | 开放协议、可自建；客户端分散，**适合作为 OSS/自托管路线** second wave |
| **WhatsApp Business** | **P2（商业）** | Meta 云 API 成熟但审核与费用门槛高；与 Telegram 用户群部分重叠 |
| **Google Chat** | **P3** | Workspace 绑定；国内可用性弱于 Teams/Slack |
| **LINE / 企业微信** | **Explore / 区域** | 强区域属性；企业微信 API 偏封闭，**默认不纳入「与 Hermes 1:1」目标** |
| **IRC / 自建 XMPP** | **OOS（默认）** | 维护成本高、用户基数小；除非客户强需求否则 **MCP/外部桥** 优先 |

## 3. 推荐顺序（实现立项时）

1. **Teams**：与 Slack 共享「工作区 + 映射 + health + serve-webhook」产品叙事，复用 **`gateway_summary_v1`** 扩展字段策略。
2. **Matrix**：若优先 OSS/联邦，先于 WhatsApp 做 spike。
3. **WhatsApp**：有明确商业客户后再开独立 issue。

## 4. 与当前代码的关系

- 新平台应复用 **`gateway_platforms_v1`** 的扩展方式（`implementation` / `label` / `env_present`），避免再引入第三套状态源。
- **不在本文范围**：具体 Bot API 字段设计（应在 **`HM-03c` 实现 issue** 中单开）。

## 5. 验收

- 产品/维护者可据本表开 **`HM-03c-impl-*`** 或等价的下一平台 epic，而无需重新调研一遍公开市场。
