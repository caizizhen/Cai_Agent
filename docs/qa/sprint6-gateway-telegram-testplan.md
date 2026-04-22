# Sprint 6 QA 测试计划：Messaging Gateway（Telegram MVP）

> 对应开发文档：`docs/HERMES_PARITY_SPRINT_PLAN.zh-CN.md` §Sprint 6  
> 对应 backlog：`docs/HERMES_PARITY_BACKLOG.zh-CN.md` §Epic S6  
> 注意：本计划包含需要真实 Telegram Bot Token 的手工用例，同时定义可 mock 的自动化用例。

---

## 1. 测试范围

| 功能 | 命令 | 类型 | 测试重点 |
|------|------|------|---------|
| gateway 命令组 | `gateway setup/start/stop/status` | 自动化 + 手工 | 命令结构与参数 |
| Telegram 消息收发 | Bot 收发消息 | 手工（沙盒 Bot） | 端到端消息链路 |
| 用户身份绑定 | allowlist 配置 | 自动化 + 手工 | 安全授权策略 |
| 跨端会话连续性 | CLI + Telegram 混合 | 手工 | 会话文件可互用 |

---

## 2. 自动化测试用例

### GTW-BASE-001：`gateway setup` 帮助信息可读
- **执行**：`cai-agent gateway setup --help`
- **期望**：exit 0，输出包含 `--token`、`--allow` 参数说明

### GTW-BASE-002：未配置时 `gateway status` 给出引导
- **前置条件**：无网关配置文件
- **执行**：`cai-agent gateway status --json`
- **期望**：exit 2，JSON 包含 `configured=false`、引导运行 `gateway setup`

### GTW-BASE-003：`gateway status` JSON 字段完整
- **前置条件**：已完成 setup（mock token）
- **执行**：`cai-agent gateway status --json`
- **期望**：包含 `running`、`bound_users`、`uptime_sec`、`last_message_at`

### GTW-SEC-001：未授权 chat_id 被拒绝（mock 层）
- **前置条件**：allowlist 中只有 chat_id=111，模拟来自 chat_id=222 的消息
- **执行**：调用网关消息处理入口（单元测试 mock Telegram API）
- **期望**：消息不触发执行，返回标准拒绝回复

### GTW-SEC-002：空 allowlist 时拒绝所有请求
- **前置条件**：allowlist=[]
- **执行**：同上，任意 chat_id
- **期望**：全部拒绝

### GTW-SEC-003：`gateway setup --allow` 追加授权
- **执行**：`cai-agent gateway setup --allow 123456 --json`（mock 模式）
- **期望**：配置文件中 `allowed_chat_ids` 包含 123456

### GTW-SEC-004：token 不写入日志或标准输出
- **执行**：`gateway setup --token BOTTOKEN123 --json`
- **期望**：stdout/stderr 中不出现完整 token 字符串（防止泄漏）

---

## 3. 手工测试用例（需真实 Telegram Bot）

> 前置条件：已通过 `@BotFather` 创建测试 Bot，获取 Token；测试人员 Telegram 账号已加入 allowlist。

### GTW-TG-001：发送文本消息，收到 answer
- **步骤**：在 Telegram 向 Bot 发送"hello"
- **期望**：Bot 回复 Agent 的 answer（几秒内）

### GTW-TG-002：长回复自动分段
- **步骤**：发送会产生长回复的问题
- **期望**：回复被分成多条消息，每条 < 4096 字符，顺序正确

### GTW-TG-003：`/new` slash 命令重置会话
- **步骤**：发送 `/new`
- **期望**：Bot 确认新会话已开始，历史上下文不带入

### GTW-TG-004：`/status` 查看当前状态
- **步骤**：发送 `/status`
- **期望**：Bot 回复当前 model、workspace、profile 信息

### GTW-TG-005：`/stop` 中断当前任务
- **步骤**：发送一个会产生长时间执行的任务，然后发送 `/stop`
- **期望**：Bot 中止执行并回复确认

### GTW-TG-006：非授权用户消息被静默拒绝
- **步骤**：用未授权账号向 Bot 发送消息
- **期望**：Bot 回复标准拒绝语，不触发 Agent 执行

### GTW-CONT-001：Telegram 会话可被 CLI 继续
- **步骤**：
  1. 在 Telegram 发起一轮对话（会自动保存 `.cai-session-tg-*.json`）
  2. 在 CLI 执行 `cai-agent continue <session-file> "继续分析"`
- **期望**：CLI 能正确加载 Telegram 会话历史并继续

---

## 4. 安全测试重点

### GTW-SEC-005：Bot Token 不出现在 config 备份中
- 检查 `export --target cursor` 等导出命令不包含明文 token

### GTW-SEC-006：DM 配对防止 Telegram 用户劫持
- 验证配对流程（如果实现），确保只有持有 pairing code 的用户可绑定

### GTW-SEC-007：消息频率限制（反滥用）
- 短时间内大量消息不导致 daemon 崩溃或无限循环

---

## 5. 回归关联

```bash
python3 -m pytest -q cai-agent/tests/test_gateway*.py
```

---

## 6. 验收信号

- 自动化用例 GTW-BASE-001~003、GTW-SEC-001~004 全部通过（P0 安全用例必须通过）
- 手工用例 GTW-TG-001~006 在沙盒 Bot 中全部通过
- gateway setup/start/stop/status 在 README 有完整使用说明
