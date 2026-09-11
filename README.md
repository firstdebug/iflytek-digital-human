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

## 使用方式

### 统一入口

虚拟人相关任务从 `avatar-workflow-entry` 开始。推荐显式调用：

```text
使用 $iflytek-digital-human:avatar-workflow-entry 帮我接入一个 Web 虚拟人对话项目
```

如果当前宿主支持 slash command，也可以使用：

```text
/avatar-workflow-entry
```

你也可以直接描述目标，入口会在确认后路由到对应 Skill，例如：

- 创建 Web 对话模板或数字人直播项目
- 在 Web、Android 或 iOS 中自建 SDK 项目
- 通过 WebAPI/WebSocket 从后端驱动虚拟人
- 配置文本、语音、音频驱动、全双工、动作、字幕或透明背景
- 配置模型/知识库，获取凭据，或排查鉴权、黑屏、无声音和网络问题

### 实际工作流

入口不是“收到关键词就直接执行”。一次完整任务通常按以下顺序推进：

1. **授权门禁**：首次进入明确的虚拟人任务时，在对话正文完整展示能力清单和统计授权说明；用户选择后生成并校验项目级 `.runtime/gate-consent.json` 准入凭证。
2. **需求澄清**：确认项目类型、目标平台（Web/Android/iOS）、接入方式、文本/语音能力和交互形态。麦克风、录音、推送说话、自动 VAD、全双工等不会由“接 SDK”自动推断，必须逐项确认。
3. **模式选择**：SDK 自建项目选择 `quick` 或 `strict`。`quick` 减少文档和计划产物，但不降低关键验证覆盖；`strict` 保留更完整的设计、计划和复核过程。
4. **预检与实施**：按路由调用凭据、SDK 产物、工具链、文本/语音/配置等 Skill，实施结果写入项目，而不是只给出代码片段。
5. **运行验证与收口**：Web SDK 必须通过浏览器运行证据（`web_runtime_evidence.py`）和交付门禁（`web_delivery.py`）；自动化证据只证明“虚拟人出现并通过文本链路回话”，不模拟麦克风、录音或全双工语音。其他平台按对应的构建/运行验证规则收口。没有真实运行证据时不会声称“已验证”。

### 直接调用下游 Skill

在已经明确需求并完成授权门禁后，也可以显式调用具体 Skill，例如：

```text
$iflytek-digital-human:avatar-text-driver
$iflytek-digital-human:avatar-voice-interact
$iflytek-digital-human:avatar-full-duplex
$iflytek-digital-human:avatar-webapi-protocol
```

下游 Skill 仍会自检 `.runtime/gate-consent.json`；准入凭证缺失、篡改或状态不一致时会拒绝实施并返回授权门禁。

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

## 目录结构与组件

```text
iflytek-digital-human/
├─ .claude-plugin/marketplace.json        # Claude Code marketplace 清单
├─ .agents/plugins/marketplace.json       # Codex marketplace 清单
├─ .cursor-plugin/plugin.json             # Cursor 插件入口清单
├─ claude/iflytek-digital-human/          # Claude Code 自包含插件包
│  ├─ .claude-plugin/plugin.json
│  ├─ skills/                             # Claude Code Skills
│  ├─ hooks/                              # Claude Code Hook 脚本
│  ├─ tools/                              # Python 平台工具
│  ├─ config/                             # 工具、隐私、遥测配置
│  └─ docs/                               # 能力清单、流程和维护文档
├─ plugins/iflytek-digital-human/         # Codex 自包含插件包
│  ├─ .codex-plugin/plugin.json
│  ├─ hooks.json                          # Codex Hook 注册
│  ├─ skills/                             # 29 个 canonical avatar-* Skills
│  ├─ tools/
│  ├─ config/
│  └─ docs/
├─ cursor/                                # Cursor / 兼容 Agent 适配包
│  ├─ skills/                             # 29 个 canonical avatar-* Skills
│  ├─ agents/
│  ├─ tools/
│  ├─ config/
│  └─ docs/
├─ tests/                                 # 跨平台一致性、门禁、安全与生命周期测试
└─ README.md
```

三个主分发包只读取各自的 manifest 和包目录：

- Claude Code：`claude/iflytek-digital-human/`
- Codex：`plugins/iflytek-digital-human/`
- Cursor：`cursor/`

各端实际版本以对应 manifest 为准，不使用 README 中的固定版本号代替发布版本。

## Skills 列表（29 个）

以下以 Codex/Cursor 适配包中的 canonical Skill 名称为准。Claude Code 包内部分早期能力仍保留短名目录，但对外文档、统计和新适配包统一使用 `avatar-*` 名称。

### 入口、门禁与工作流

- `avatar-workflow-entry`：统一入口，负责能力说明、授权门禁、意图识别和路由。
- `avatar-consent-gate`：隐私授权硬门禁，生成并校验 `.runtime/gate-consent.json` 准入凭证。
- `avatar-brainstorming`：需求澄清阶段，确认目标平台、接入方式、功能边界和交付模式。
- `avatar-planning`：计划生成阶段；`quick` 模式可跳过重文档，`strict` 模式保留完整计划。
- `avatar-executing`：执行实现阶段，根据已确认方案调用工具和平台 Skill 落地项目。
- `avatar-verification`：交付前验证，检查构建、运行证据、关键文件和剩余问题。
- `avatar-shared`：共享材料容器，包含 TDD、并行分发、Android 分区存储等复用规范。

### 接入准备与平台配置

- `avatar-credentials`：登录平台、查询应用/场景、获取并安全写入凭据。
- `avatar-preflight`：开发环境门禁，分层检查凭据、资源授权、SDK、网络和工具链。
- `avatar-toolchain`：按 Web/Android/iOS 检查 Node、Gradle、Xcode 等工具链状态。
- `avatar-artifact-download`：下载并校验 Web/Android/iOS SDK 产物与本地清单。
- `avatar-config-authoring`：调整分辨率、码率、帧率、形象、发音人、TTS 参数和背景。
- `avatar-model-config`：绑定、发布或创建自有模型，处理官方模型与 OpenAI 兼容模型配置。
- `avatar-knowledge-base`：创建知识库、上传文档、配置 docqa/RAG 调用链并发布场景。

### 应用创建与协议接入

- `avatar-web-template`：创建官方 Web/H5 对话模板应用，适合零代码生成可访问链接。
- `avatar-live-streaming`：创建数字人直播项目，配置商品、分镜、脚本并发布直播间。
- `avatar-webapi-protocol`：不使用 SDK，直接按 WebSocket 报文协议接入虚拟人服务。
- `avatar-integration-guides`：Web/Android/iOS 三端 SDK 快速理解索引，真正交付以执行 Playbook 为准。

### SDK 交互能力

- `avatar-text-driver`：文本驱动，让数字人播报指定文本，不经过 NLP 对话。
- `avatar-text-interact`：文本交互，接入 NLP/大模型对话后驱动数字人回复。
- `avatar-audio-driver`：音频驱动，用音频数据直接驱动口型和播报。
- `avatar-voice-interact`：语音交互，处理麦克风、录音、ASR、NLP、TTS 的短语音链路。
- `avatar-full-duplex`：全双工与打断，处理持续拾音、实时识别、VAD 和可打断播报。
- `avatar-action-control`：动作控制，包含独立动作和自动动作 AIR。
- `avatar-subtitle-setup`：字幕配置和显示。
- `avatar-transparent-bg`：透明背景配置。

### 故障排查

- `avatar-troubleshoot`：错误码、黑屏、连接失败、鉴权失败、WebSocket 1008 等问题诊断与修复。
- `avatar-permissions-setup`：浏览器或移动端录音、麦克风、摄像头权限配置。
- `avatar-network-debug`：WSS 连通性、DNS、代理、防火墙和服务端网络问题排查。

## Tools 说明

所有平台工具位于各分发包的 `tools/` 目录，并通过 `config/tools.yaml` 登记。常用工具如下：

- `telemetry.py` / `telemetry_common.py` / `uploader.py`：授权状态、workflow/invocation 生命周期、本地状态和异步上报。
- `xfyun_common.py`：登录、Cookie 管理和统一 HTTP 请求封装；Cookie 可用环境变量改存储位置。
- `xfyun_query_services.py`：查询账号下的应用、场景、sceneId、appId 和脱敏后的 API 信息。
- `xfyun_template.py`：创建、配置、发布 Web/H5 对话模板应用，可生成访问链接和配置页。
- `xfyun_live.py`：创建虚拟人直播项目，配置直播场景、商品、分镜、脚本和发布链接。
- `xfyun_model_manage.py`：模型列表、能力检查、官方/自有模型绑定、发布和密钥更新。
- `xfyun_knowledge.py`：知识库标签、建库、文档上传、版本查询、场景启用和调用链配置。
- `xfyun_secrets.py` / `write_env_safe.py`：密钥脱敏、加密存储、安全输入和 `.env` 写入。
- `sdk_artifact.py`：SDK 产物发现、下载记录和完整性校验。
- `websocket_auth.py`：生成 Web SDK canonical signed URL handler，避免模型手写 HMAC。
- `web_runtime_evidence.py`：用 Playwright 打开页面、点击启动并采集连接、首帧和交互证据。
- `web_delivery.py` / `web_sdk_gate.py` / `completion_check.py`：Web SDK 项目交付门禁、运行证据判断和最终完成条件检查。
- `platform_endpoints.py` / `xfyun_interface.py`：平台端点、接口场景和资产授权相关辅助工具。

工具输出默认做敏感信息脱敏。Cookie、API Key、API Secret、`.env`、`.runtime/` 和 telemetry 本地状态都不应提交到 Git。

## 跨平台支持

- **Claude Code**：使用自包含插件和宿主 Hook；Hook 负责提示/门禁辅助，业务流程仍由入口 Skill 和 telemetry 工具完成。
- **Codex**：使用 `plugins/iflytek-digital-human/` 自包含包和 `hooks.json`；安装或升级后建议新建任务。
- **Cursor**：使用 `cursor/` 适配包；不假设具备 Claude Code 的完整生命周期 Hook，因此依赖显式入口和工具命令完成门禁、生命周期和验证。
- **AStudio 或其他兼容 Agent**：可以复用 Cursor/Codex 适配包。为让统计中的客户端来源准确，请在宿主启动工具前设置 `IFLYTEK_DIGITAL_HUMAN_AGENT=astudio`；该字段只表示宿主来源，不表示模型。

三个宿主的 Skill 文件遵循同一套能力和门禁约定，但安装路径、Hook 能力和会话生命周期由宿主决定，不能把某一端的 Hook 行为推定到其他端。

## 依赖与验证

平台工具需要 Python 3.8 或更高版本。进入对应插件包目录后执行：

```bash
pip install -r tools/requirements.txt
playwright install chromium
```

只有涉及网页登录或 Web SDK 浏览器运行证据时才需要 Playwright Chromium；纯文本、配置、WebAPI 或本地静态检查不需要启动浏览器。

仓库测试可以这样运行：

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m unittest discover -s plugins/iflytek-digital-human/tests -p "test_*.py"
```

## 作为开发者

如果要扩展或修改 Skills，优先改源包并保持三端分发一致：

1. 明确目标宿主：Claude Code 改 `claude/iflytek-digital-human/`，Codex 改 `plugins/iflytek-digital-human/`，Cursor/AStudio 改 `cursor/`；跨端能力变更要同步对应包。
2. 修改 `skills/<skill>/SKILL.md` 时，保持 frontmatter 的 `name` 与目录名一致，避免使用旧的未加 `avatar-` 前缀名称。
3. 新增或调整平台工具时，同步更新 `tools/`、`config/tools.yaml` 和对应 Skill 引用。
4. 涉及隐私、门禁、telemetry、Hook、Web 运行证据或凭据处理时，补充 `tests/` 下的跨平台测试。
5. 提交前至少运行根目录测试；如果改了 Codex 包，也运行包内测试。

## 安全约束

- 不要提交 `.runtime/`、`telemetry/`、Cookie、`.env` 或任何平台密钥。
- Web 生产接入必须在服务端生成签名，不要把 `apiSecret` 写入前端。
- 登录态、凭据和运行证据属于本机状态，不应复制进插件发布包。

## License

MIT
