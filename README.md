# iflytek-digital-human

讯飞虚拟人交互平台接入插件，为 Claude Code、Codex 和 Cursor 提供统一的虚拟人任务入口、平台工具和交付验证流程。

- 插件 ID：`iflytek-digital-human`
- 统一入口：`avatar-workflow-entry`
- GitHub：<https://github.com/firstdebug/iflytek-digital-human>
- 讯飞虚拟人平台：<https://virtual-man.xfyun.cn/>

> 原插件 ID 和仓库名为 `avatar-platform`。升级时应先卸载或禁用旧插件，避免新旧 Skill 或 Hook 同时加载。仓库地址已经迁移到 `firstdebug/iflytek-digital-human`，旧地址不再作为安装入口。

## 能力范围

- Web 对话模板与数字人直播
- Web、Android、iOS SDK 自建项目
- WebAPI/WebSocket 报文接入
- 文本交互、语音交互、音频驱动、全双工与动作控制
- 模型配置、知识库、凭据获取和故障排查
- SDK 产物下载、环境预检和交付验证

插件只应处理明确的讯飞虚拟人或数字人任务。普通后端开发以及单独的 `NlpMessage`、`nlp-svc`、OpenAI SSE 或 Higress 调试不应触发本插件。

## 获取源码

```bash
git clone https://github.com/firstdebug/iflytek-digital-human.git
cd iflytek-digital-human
```

## 安装

### Claude Code

```bash
claude plugin marketplace add https://github.com/firstdebug/iflytek-digital-human.git
claude plugin install iflytek-digital-human@iflytek-digital-human-marketplace
claude plugin list
```

安装或更新后请重新启动 Claude Code 或新建会话，使新的 Skill 和 Hook 生效。

### Codex

```bash
codex plugin marketplace add firstdebug/iflytek-digital-human --ref main
codex plugin add iflytek-digital-human@iflytek-digital-human-codex
codex plugin list
```

安装或更新后请新建 Codex 任务。`codex plugin list` 应显示：

```text
iflytek-digital-human@iflytek-digital-human-codex  installed, enabled
```

### Cursor

1. 打开 Cursor Dashboard 的 `Plugins` -> `Team Marketplaces`。
2. 选择 `Add Marketplace` -> `Import from Repo`。
3. 输入 `https://github.com/firstdebug/iflytek-digital-human.git`。
4. 在 `Customize` -> `Plugins` 或 `Customize` -> `Skills` 中确认 `iflytek-digital-human` 已启用。

也可以把 `cursor/skills/` 复制到项目的 `.cursor/skills/` 或用户目录 `~/.cursor/skills/`。

## 从旧插件迁移

仅在旧插件仍存在时执行对应宿主的卸载命令，再安装新插件：

```bash
# Claude Code
claude plugin uninstall avatar-platform@avatar-platform-marketplace
claude plugin marketplace remove avatar-platform-marketplace

# Codex
codex plugin remove avatar-platform@avatar-platform-codex
codex plugin marketplace remove avatar-platform-codex
```

旧的本地统计状态可能从 `avatar-platform/telemetry` 迁移到 `iflytek-digital-human/telemetry`。不要同时启用新旧插件。

## 使用

可以显式调用统一入口：

```text
使用 $iflytek-digital-human:avatar-workflow-entry 帮我创建一个 Web 虚拟人对话项目
```

如果宿主把 Skill 暴露成 slash command，也可以使用：

```text
/avatar-workflow-entry
```

也可以直接描述明确需求，例如：
- 创建 Web 智能客服虚拟人
- 在 Android 应用中接入讯飞虚拟人 SDK
- 通过 WebAPI 从后端驱动虚拟人
- 配置外部大模型或讯飞知识库
- 排查鉴权、黑屏、无声音或网络问题

首次 SDK 自建会确认目标平台、文本/语音等功能边界及 `quick` 或 `strict` 交付模式。新增麦克风、录音或全双工能力必须单独取得确认，不能由“接 SDK 自建”自动推断。

## 使用统计与隐私

首次进入明确的虚拟人任务且授权状态未决定时，插件必须在助手对话正文中完整展示能力清单和使用统计授权说明，再等待用户选择“同意使用统计”或“不同意使用统计”。工具输出、隐藏上下文或只给文件路径不算展示。

- 不同意统计不会影响插件功能。
- 沉默、继续使用或关闭提示均不视为同意。
- 不收集对话全文、Prompt 原文、代码、绝对路径、密码、Cookie、Token、API Key 或 API Secret。
- Claude Code 与 Codex 通过宿主 Hook 加强路由和授权门禁；Cursor 由入口 Skill 显式执行同一流程。

完整声明由各平台包内的 `config/privacy_notice.json` 和 `tools/telemetry.py notice` 生成。

在没有可靠 Hook 的宿主中，授权选择会由工具写入当前项目的
`.runtime/gate-consent.json`。后续实施前必须执行：

```bash
python tools/telemetry.py consent --status
python tools/telemetry.py consent --validate-gate --project "<项目目录>"
```

只有 `valid (accepted)` 或 `valid (declined)` 才能继续；缺失、篡改或状态不一致会回到授权门禁。
Hook 仅在当前消息显式调用 `$iflytek-digital-human:avatar-<skill>`、`$avatar-<skill>`
或 `/iflytek-digital-human:avatar-<skill>` 时启用。自然语言、引用历史、代码块不会触发。

## 仓库结构

```text
iflytek-digital-human/
├─ .claude-plugin/marketplace.json       # Claude Code marketplace
├─ .agents/plugins/marketplace.json      # Codex marketplace
├─ .cursor-plugin/plugin.json            # Cursor 插件清单
├─ claude/iflytek-digital-human/         # Claude Code 自包含插件
├─ plugins/iflytek-digital-human/        # Codex 自包含插件
├─ cursor/                               # Cursor 适配包
├─ tests/                                # 跨平台一致性与安全测试
└─ README.md
```

三个宿主只读取各自的 manifest 和包目录：

- Claude Code：`claude/iflytek-digital-human/`
- Codex：`plugins/iflytek-digital-human/`
- Cursor：`cursor/`

各端实际版本以对应 manifest 为准，不使用 README 中的固定版本号代替发布版本。

## 运行依赖

平台工具需要 Python 3.8 或更高版本。进入对应插件包目录后执行：

```bash
pip install -r tools/requirements.txt
playwright install chromium
```

只有涉及网页登录或浏览器运行证据时才需要 Playwright Chromium。

## 安全约束

- 不要提交 `.runtime/`、`telemetry/`、Cookie、`.env` 或任何平台密钥。
- Web 生产接入必须在服务端生成签名，不要把 `apiSecret` 写入前端。
- 登录态、凭据和运行证据属于本机状态，不应复制进插件发布包。

## License

MIT
