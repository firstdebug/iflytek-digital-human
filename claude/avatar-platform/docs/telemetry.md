# avatar-platform 使用统计说明

## 收集什么

| 项目 | 说明 |
|---|---|
| 匿名标识 `anonymous_id` | 本机机器 ID 经 SHA-256 截断得到的 16 位十六进制值 |
| skill 名称 | 一个工作流使用过哪些 skill；重复 Read 不重复计数 |
| 工作流类型与状态 | 如 `sdk_integration` / `web_template`，状态 `completed` / `interrupted` / `failed` |
| 时间戳 | 工作流开始、结束时间 |
| 环境 | 操作系统类型（如 `win32`）、插件版本 |
| 讯飞账号标识 | **仅在你登录讯飞平台后**，在本地哈希 account_id，原始值不入库、不上传 |

### 关于 anonymous_id

取值来源按平台：

- Windows — 注册表 `HKLM\SOFTWARE\Microsoft\Cryptography` 下的 `MachineGuid`
- macOS — `IOPlatformUUID`
- Linux — `/etc/machine-id`

**原始机器 ID 不会被记录、不会离开本机。** 只有 SHA-256 哈希的前 16 位会入库和上报，
无法从哈希值反推出机器 ID。取不到机器 ID 时退化为随机 UUID。

该值首次计算后写入 `~/.claude/avatar-platform/telemetry/anonymous_id.json`，之后只读该文件。
删除此文件或更换设备会被视为新用户，因此"用户总数"是一个略微高估的近似值。

## 不收集什么

- 密码、Access Token、Refresh Token、Cookie
- `apiKey`、`apiSecret` 及任何认证凭据
- 代码内容、文件内容
- 单次 Prompt 和对话全文（同意后仅在本地内存做关键词匹配，不落盘、不上传）
- 接口请求参数与响应原文
- 完整命令行参数
- 项目绝对路径会在本地用于工作流接续和产物验证，但不写 debug、不上传；不收集 Git 仓库地址、Git 用户名与邮箱

## 数据存在哪

用户明确同意后，数据先写入本地待上传队列，再批量发送到隐私声明列出的接收地址。本地路径：

```
~/.claude/avatar-platform/telemetry/
├── state.json          workflow、invocation 和上传状态机
├── state.lock          跨进程写锁
├── uploader.lock       uploader 单实例锁
├── anonymous_id.json   匿名标识
└── consent.json        你的同意记录
```

声明内容来自 `config/privacy_notice.json`。法律依据为讯飞开放平台
[隐私政策](https://www.xfyun.cn/doc/policy/privacy.html#%E4%B8%80%E3%80%81%E5%AE%9A%E4%B9%89%E4%B8%8E%E8%A7%A3%E9%87%8A)
与[用户服务协议](https://www.xfyun.cn/doc/policy/agreement.html)；插件声明只补充本插件使用统计的采集范围。
没有同意记录时状态为 `undecided`；声明内容或地址
变化会改变摘要，已有同意自动转为 `stale`，重新同意前停止采集和上传。

## 开关

```bash
# 启用（未启用时不采集任何数据）
python tools/telemetry.py consent --accept

# 关闭
python tools/telemetry.py consent --decline

# 查看说明
python tools/telemetry.py notice

# 查看状态：undecided / stale / accepted / declined
python tools/telemetry.py consent --status

# 本地查看已采集的统计
python tools/telemetry.py stats
```

默认**未启用**。只有完整展示当前版本声明、用户明确选择同意，并且同意记录与声明摘要及
上报地址一致时才启用。其余状态下 Hook 在检查 Prompt/tool_input 前立即退出，不读机器 ID、
不写状态文件、不写 debug、不启动上传器。

拒绝或撤回时会清除匿名标识、状态机、待上传数据和诊断日志，只保留不含设备信息的
`consent.json` 拒绝记录，防止反复询问。拒绝不影响插件任何业务功能。

## 采集机制

三条路径，两个 hook 事件：

| 用户/模型行为 | Hook | 识别方式 |
|---|---|---|
| 输入 `/avatar-platform:xxx` | `UserPromptSubmit` | prompt 文本正则 |
| 模型调用 Skill 工具 | `PreToolUse` | `tool_name == 'Skill'` |
| 模型读取 skill 的 `SKILL.md` 或 `references/scripts/templates/assets` | `PreToolUse` | `tool_name == 'Read'` + 受限路径正则 |

第三条是主路径 —— avatar-platform 的多数 skill 未注册为可发现 skill，
工作流中间步骤既可能读取 `SKILL.md`，也可能直接读取其 reference 或脚本；都归到父 skill 的 invocation。项目文件即使位于插件目录，也不会因普通路径名被误记。

### 上传时机

| 时机 | 上传内容 | 是否强制 |
|---|---|---|
| `UserPromptSubmit` 识别并创建或续接有效工作流后 | 当前 `in_progress` workflow；若本机已有讯飞登录 Cookie，同时带账号哈希 | 否，后台异步上传并遵守失败退避 |
| `PreToolUse` 的 Skill / Read | 先原子更新本地 workflow/invocation，再异步启动 uploader | 否，Hook 不等待网络 |
| `Stop`（一轮回复结束） | 补传本轮累计但尚未确认的数据 | 否，后台异步上传并遵守失败退避 |
| Reporter `complete` / `fail`、`SessionEnd` 或遗留工作流收口 | 重传最终 `completed` / `failed` / `interrupted` 状态及累计调用 | 是，后台异步启动并跳过退避门槛 |

因此同一 `workflow_id` 通常会至少上报两次：开始时先让服务端看到 `in_progress`，
结束时再用同一个 ID 幂等更新为终态。服务端确认前，本地记录保持 `upload_status=pending`，等待后续重试。
若用户未同意、撤回同意，或声明状态变为 `stale`，上述所有采集和上传都会停止。

### 数据质量标记

每个工作流保留 `has_avatar_signal`，表示出现过斜杠命令、Skill 工具调用，或 prompt 命中虚拟人关键词。
只有带该信号的 workflow 才进入默认统计；当前 JSON 方案不再维护 `has_real_side_effect`。

## 完成状态如何判定

两条独立路径，**扫盘优先于自报**：

### 路径一：扫盘（不依赖模型）

`SessionEnd` 时由 `tools/completion_check.py` 检查真实产物，按优先级取最强证据：

| 判据 | 检查内容 | method | 可信度 |
|---|---|---|---|
| SDK 验证结果 | `.runtime/verification-result.json` 新鲜且 `ready_to_deliver=true` | `verification_flag` | high |
| 平台侧交付物 | 非 SDK workflow 的 `.runtime/artifacts.json` 含 `template_url`/`live_url`/`lib_id` 等 | `artifacts_file` | medium |
| 凭据配置 | 凭据 workflow 的 `.env` 至少有 appId 和密钥键，值不读取不上报 | `artifact` | high |

只读固定路径，不遍历工程。mtime 门禁排除上次 workflow 的残留标记。SDK workflow 不接受 `artifacts.json`、`.env` 或 Reporter 自报作为完成证据。

### 路径二：skill 主动上报

以下 5 个终局 skill 在收尾时调用 `telemetry.py complete`：

| skill | workflow_type | 上报前置条件 |
|---|---|---|
| `avatar-verification` | `sdk_integration` | `web_sdk_gate.py` 退出码 0，并用 `--project` 指向验证结果目录 |
| `avatar-web-template` | `web_template` | 链接已生成并发布成功 |
| `avatar-live-streaming` | `live_streaming` | 直播间已发布 |
| `avatar-webapi-protocol` | `webapi_protocol` | demo 连接建立且收到有效响应 |
| `avatar-troubleshoot` | `troubleshoot` | **仅当**整段对话的原始诉求就是排障、且已验证修复、且未被其他终局 skill 上报过 |

上报时仍会检查固定证据。SDK 未找到新鲜的 `verification_flag` 时直接返回 `needs_runtime_verification`，workflow 保持 `in_progress`。其他 workflow 也只在命中各自确认完成证据后才收口。

`avatar-executing` **不**上报 —— 它后面还要走 verification，在此上报会虚报。
`avatar-config-authoring` 不上报 —— "配置改对了"无客观产物可验。

`telemetry.py stats` 按 `status=completed` 统计完成；SDK workflow 只有新鲜的
`verification_flag` 才能写成 `completed`，因此不依赖客户端自报可信度字段。

## 已知限制

- **工作流边界不等于会话边界。** 同设备、同项目目录、最近活动在 5 分钟内、无有效完成证据且状态为
  `in_progress/interrupted`，或曾被错误完成证据关闭时，新会话继续使用原 `workflow_id` 并清掉错误完成证据；切换主交付路径时旧工作流
  标记为 `cancelled`，再创建新工作流。当前 workflow 已是 `completed/failed/cancelled` 时，
  后续有效业务 Prompt 直接创建新 `workflow_id`，旧终态保持不变；例如真正完成的 Web Template 后
  再构建 SDK，必须记录为两个独立 workflow。
- **完成状态偏低估。** 扫不到产物、skill 又没上报时记为 `interrupted`。低估比高估安全，
  但完成率应理解为下界。
- **用户总数偏高估。** 见上文 anonymous_id 说明。
- **纯咨询式使用可能计入。** 只要命中虚拟人意图或实际读取 Skill，就可能形成 workflow；后端分析时应结合状态与 invocation 判断。
- **`troubleshoot` 的上报条件依赖模型自我判断。** "整段对话是否就是为了排障"没有客观判据，
  存在漏报与重复上报的可能。
