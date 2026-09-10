---
name: avatar-workflow-entry
description: >-
  【讯飞虚拟人/数字人任务的必经入口 — 任何虚拟人相关请求都必须先调用本 skill 再响应】处理一切与讯飞虚拟人/数字人（xfyun
  avatar）有关的需求：构建/搭建/做一个虚拟人项目或应用、从零创建/接入虚拟人、把虚拟人集成到
  web/android/ios、Web对话模板、数字人直播、WebAPI报文接入、语音/文本/音频驱动、配置调整、故障排查，以及"你能做什么/有哪些功能"这类能力询问。本
  skill 负责意图识别与智能路由，分发到对应子技能。触发词：构建虚拟人、搭建虚拟人、虚拟人项目、创建虚拟人、数字人、虚拟人集成、avatar、avatar
  SDK、讯飞虚拟人、xfyun、virtual-man、数字人直播、虚拟主播、你能做什么、有哪些功能、功能清单。收到上述任一信号时不要用通用知识直接回答或抛技术选型问题（如
  Unity/Three.js/2D-3D），必须先走本入口路由。
---

# avatar-workflow-entry: 智能路由入口

## 第一步：调用 `avatar-consent-gate`

在读取本入口其余内容、扫描工程、询问 `quick/strict` 或意图识别前，必须先调用
`avatar-consent-gate`。只有 `python tools/telemetry.py consent --validate-gate` 返回
`valid (accepted)` 或 `valid (declined)`，才允许继续；缺少或无效的
`.runtime/gate-consent.json` 必须立即回到该门禁。

## ⚙️ 技能库位置（路由前必读）

本入口是 iflytek-digital-human 技能包的总入口。整个技能库在固定位置：

**根目录：`${CLAUDE_PLUGIN_ROOT}`**（当前已加载的 `iflytek-digital-human@skills-dir` 插件目录，Claude Code 自动解析为真实路径）
- 业务 skill：`skills/<name>/SKILL.md`（全部大写 SKILL.md）
- 跨领域方法论：`skills/shared/` 下 2 个（测试驱动开发、并行分发子 agent），执行时应用，不在路由表内
- 平台脚本：`tools/xfyun_*.py`｜工具注册表：`config/tools.yaml`｜平台能力矩阵：`config/platform-registry.yaml`

**唯一来源门禁**：只读取当前 `${CLAUDE_PLUGIN_ROOT}` 下的文件。禁止扫描或读取
`~/.claude/iflytek-digital-human`、`~/.claude/backups/*/iflytek-digital-human`、
`~/.claude/plugins/cache/*/iflytek-digital-human`、旧 marketplace 副本或工作目录中的同名副本。
这些路径不是当前插件，不得作为 Skill、Playbook、端点、命令或上报规则的来源。
当前插件内的全部业务 Skill 保留并按本入口路由；不要因为只允许终局上报就删除本插件内的支持 Skill。

**注册事实**：当前 `iflytek-digital-human@skills-dir` 的全部 28 个 Skill 都由 Claude Code 注册为可发现组件。
优先通过 Skill 调用目标；需要读取详细 Playbook 时，只读取
`${CLAUDE_PLUGIN_ROOT}/skills/<目标名>/SKILL.md`（文件名大小写固定），不得搜索其他安装或缓存目录。

## 定位

虚拟人集成任务的**统一入口**，负责快速识别任务类型并路由到对应技能。

## 调用时机

- 用户提出虚拟人相关需求
- 明确的问题场景（故障排查、配置调整）
- 模糊的需求场景（需要澄清）

---

## 首次调用：能力清单 + 完整声明（隐私授权门禁，HARD-GATE：先于业务路由）

`UserPromptSubmit` Hook 会在上下文中注入：

```text
[iflytek-digital-human consent] status=<accepted|declined|undecided|stale>
```

这是本插件第一次有效调用的硬门禁，必须早于快速扫描工程、quick/strict 询问、意图识别和任何下游 skill。
在快速扫描工程或调用任何下游 skill 前，优先使用该状态，不再执行重复检查：

- 已是 `accepted`：不要运行 `telemetry.py consent --status`，不要向用户提及或重复询问授权，直接继续业务路由。
- 已是 `declined`：不要运行 `telemetry.py consent --status`，不要重复提示；保持统计关闭并继续业务路由。
- `undecided` 或 `stale`：不要重复检查状态，按下面固定顺序一次完成首次调用门禁：
  1. 读取 `${CLAUDE_PLUGIN_ROOT}/docs/capabilities.md`，将文件完整内容作为“我能做什么”原样展示（允许排版，不得增删、缩写或编造能力）。
  2. 运行 `python "${CLAUDE_PLUGIN_ROOT}/tools/telemetry.py" notice`（即 `telemetry.py notice`），将命令输出的完整声明原文紧接着展示；不得手写、概括或缩短声明。声明中的《讯飞开放平台隐私政策》与《讯飞开放平台用户服务协议》链接必须原样保留，不得改成其他地址。
  3. 使用 `AskUserQuestion` 只提供两个选项：“同意使用统计”和“不同意使用统计”。说明不同意不影响虚拟人功能；沉默、继续提需求或关闭提示都不算同意。
  用户选择前停止：不得扫描工程、不得询问 quick/strict、不得调用下游 skill、不得实施业务。

当用户问的就是“你能做什么/有哪些功能”时，`accepted` 或 `declined` 只展示能力清单：读取上述 `docs/capabilities.md` 的完整内容，不重复声明和授权问题；`undecided` 或 `stale` 仍须按能力清单→完整声明→二选一的顺序执行。

仅当上下文中没有 `[iflytek-digital-human consent]`，或状态为 `unavailable` 时，才回退运行：

```bash
python "${CLAUDE_PLUGIN_ROOT}/tools/telemetry.py" consent --status
```

回退命令必须静默执行；确认返回 `undecided` 或 `stale` 之前，不要先对用户说“需要确认数据授权”。

只有用户明确选择“同意使用统计”后，才能运行 `telemetry.py consent --accept`。用户选择“不同意使用统计”时运行
`telemetry.py consent --decline`；沉默、跳过、继续提业务需求或任何含糊回答都不得视为同意。

**首次同意后的固定补偿顺序（HARD-GATE）**：`consent --accept` 成功后，必须立刻重新读取本入口
`${CLAUDE_PLUGIN_ROOT}/skills/avatar-workflow-entry/SKILL.md`，让这次入口使用在
授权之后形成真实的 `read` invocation。此时 workflow / invocation 只写入本地 pending 状态，不立即上传，
也不得直接运行 `uploader.py --force`。后续业务 Skill 走登录或获取 appId、apiSecret 的链路时，只有本地
Cookie 同时存在 `account_id` 和 `ssoSessionId`，才由 `xfyun_common.py` 异步触发上传；`ssoSessionId`、
Cookie 和密钥本身绝不进入上报报文。不得把授权前的 slash/prompt 追溯写入或伪造为已授权事件；如果用户拒绝，
不得重新读取入口或运行上传器。已是 `accepted`、`declined` 的后续请求不重复执行这段补偿流程。

完成授权判断后继续用户原本的业务请求，不把同意作为使用插件功能的前提。

---

## 核心工作流概览

三步完成路由决策：

1. **快速扫描工程** — 检测 SDK 集成状态（未集成 / 部分 / 完整）与平台（web / android / ios / unknown）
2. **意图识别** — 结合关键词、指标、工程扫描结果输出意图类型与置信度
3. **路由决策** — 按置信度阈值决定直接路由、询问确认或回退完整流程

完整代码实现见 `references/routing-flow.md`。

---

## 用户确认门禁（HARD-GATE：必须先问，不能默认）

这两个门禁在路由阶段就要判定，**不得**因为需求看起来明确而跳过。

### 1. 交付模式门禁（workflow_mode）

首次 SDK 自建、从零构建或多能力扩展，**必须**先用 `AskUserQuestion` 让用户选择
`workflow_mode: quick | strict`，规则见 `../shared/delivery-modes.md`。

- 用户未选择时**停止实施**，不能默认 `quick`，也不能把"推荐 quick"当作用户已选择。
- 用户明确说"快速做、先跑起来、少文档、不要 reviewer"→ `quick`，不重复询问。
- 用户明确说"完整设计、严格流程、要审计"→ `strict`，不重复询问。
- 已有项目的单一配置修改或故障修复默认 `quick`，无需提问。
- 把选择结果连同项目路径、平台、功能边界一起传给下游 skill。

| 模式 | 流程 | 默认产物 |
|------|------|----------|
| `quick`（推荐） | `avatar-brainstorming` 形成内存实施摘要 → `avatar-executing` 主 agent 直接实现 | 工程 + 构建/运行结果，不生成过程文档 |
| `strict` | `avatar-brainstorming` → `avatar-planning` → `avatar-executing`，含 spec/plan/code 评审 | 工程 + 设计 + 计划 + 完整验证报告 |

### 2. 语音能力门禁

新增语音识别、语音问答、录音、麦克风权限或语音 UI 前，**必须**单独用 `AskUserQuestion`
征得用户确认，并同时确认交互形态：**按住说话 / 点击开始停止 / 自动 VAD / 全双工**。

- 用户确认前**不得**修改 AndroidManifest.xml 或 Info.plist、**不得**加入 `RECORD_AUDIO`、
  **不得**加入录音代码或语音 UI。
- 用户只要求文本对话时，**不得**自行添加语音功能。
- "给现有项目加语音"即使工程和目标明确，也要先问一次形态再实施。
- 未确认的能力必须写入实施摘要的 `excluded`。

这两个门禁在 `avatar-executing`、`voice-interact` 和 `avatar-permissions-setup` 中同样强制执行，
防止绕过本入口直接实施。

---

## 决策分支（场景 → 路由目标）

| 场景 | 典型信号 | 路由目标 | 优先级 |
|------|----------|----------|--------|
| 故障排查 | 失败/报错/黑屏、错误码、日志、`avatar authentication failed`、1008/10113/10114/10120/10121 | avatar-troubleshoot | highest |
| 权限问题 | 权限拒绝、麦克风/摄像头 | avatar-permissions-setup | high |
| 网络问题 | 连接/超时/断开、10200/10201 | avatar-network-debug | high |
| 配置调整 | 调整/修改、分辨率/码率/形象 | avatar-config-authoring | high |
| Web 对话模板 | 智能客服/H5/大屏、用模板快速生成对话页 | avatar-web-template | high |
| 数字人直播 | 直播间/虚拟主播/带货/分镜 | avatar-live-streaming | high |
| WebAPI 报文接入 | WebAPI/web api/报文/协议/不用SDK/直连WebSocket/请求响应/ctrl/event_type | avatar-webapi-protocol | high |
| 知识库管理 | 知识库/docqa/RAG/上传文档/知识问答/文档检索 | avatar-knowledge-base | high |
| 首次接入 | 集成/接入/从零、SDK 未集成 | avatar-brainstorming | medium |
| 功能扩展 | 添加/新增、语音交互/动作控制 | avatar-brainstorming | medium |
| 文档查询 | 如何/怎么、无实施意图 | provide_docs | low |

- 完整关键词 / 指标映射：见 `references/routing-rules.md`
- 各路由目标的输入 / 输出说明：见 `references/route-targets.md`
- 各置信度下的完整示例：见 `references/examples.md`

鉴权错误特例：命中 `avatar authentication failed`、`authorization invalid`、WebSocket 1008 或
10110/10113/10114/10120/10121 时，路由到 `avatar-troubleshoot`，并要求其读取
`references/authentication-failed.md`。不得直接回复“重新复制凭据”或“发布场景”，也不得把通用鉴权失败
改路由成纯网络问题；先取得平台错误说明、关闭码或 app/scene/授权查询证据再定因。

---

## 外部LLM + 讯飞知识库集成（路由增强：识别后按原生链路处理）

**触发条件**：用户需求中**同时**出现以下信号：
- 外部LLM关键词：DeepSeek / GPT / Claude / ChatGPT / 通义千问 / 文心一言 / 外部模型 / 第三方模型
- 讯飞能力关键词：讯飞知识库 / docqa / NLP / 星火 / 虚拟人对话 / 大模型对话

**关键事实（不是冲突）**：讯飞平台支持把外部 LLM（DeepSeek/GPT 等）注册为**自有模型**
（`python tools/xfyun_model_manage.py create`，modelType=2，`nlpType=openai`，走 OpenAI 兼容端点）。知识库（docqa）
的检索结果可以通过调用链 `docqa,<自有模型>` 灌给这个外部模型生成答案——**并非只能对接星火**。
调用链 `nlpAssistantInfo` 是**原样可配置字符串**，`docqa,openai` 与 `docqa,xinghuo` 同等有效。

**原生集成链路（DeepSeek + 健身知识库为例）**：
1. `python tools/xfyun_model_manage.py create <name> <model> <introduce> <apiUrl>` 注册 DeepSeek；apiKey 交互输入，nlpType 为 `openai`
2. `python tools/xfyun_model_manage.py bind <sceneId> <modelName>` 把 DeepSeek 绑定到场景
3. `python tools/xfyun_knowledge.py create-kb <name>` 与 `upload <libId> <file...> --wait` 建库并上传文档
4. `python tools/xfyun_knowledge.py enable <sceneId> <libId> --chain docqa,openai` 关联知识库并默认自动发布
5. 用 `xfyun_knowledge.py status`、`xfyun_model_manage.py query` 和 `query-interact` 验证知识库、模型与 `docqa,openai` 链路

**处理流程**：
- 识别到该组合 → **不中断路由**，直接路由到 `avatar-brainstorming`（首次接入/建项目）或
  `avatar-knowledge-base`（已有场景只需配知识库），并在规划中标注"DeepSeek 走自有模型 + `docqa,openai` 链路"
- 仅当用户明确表示"不想把密钥托管到讯飞平台/要完全自建 RAG"时，才改走 App/后端自建 RAG 方案

**HARD-GATE**：给外部 LLM 挂知识库时，`enable`/`chain` 的调用链第二段**必须**是绑定模型的
nlpType（自有模型=`openai`），写成 `docqa,openai`。沿用默认 `docqa,xinghuo` 会导致知识库检索
结果被喂给星火而非 DeepSeek。

**示例**：
```
用户："构建基于健身知识库的虚拟人对话安卓项目，用DeepSeek模型"
检测到：DeepSeek(外部LLM) + 知识库(讯飞能力) → 原生可集成，无需自建RAG
输出：路由到 avatar-brainstorming，标注"DeepSeek 注册为自有模型(openai) + docqa,openai 链路挂健身知识库"
```

---

## 交付形态澄清（HARD-GATE：宽泛"构建对话项目"需求）

当用户表达的是**宽泛的"构建 / 搭建 / 做一个 虚拟人对话项目 / 应用"**，且**未指明交付形态**时，
**不要**默认跳进 SDK 自建（avatar-brainstorming）访谈。先用 `AskUserQuestion` 澄清路径，再路由：

| 路径 | 交付物 | 路由目标 | 适合 |
|------|--------|----------|------|
| 官方模板 | 零代码、开箱即用的可访问链接 | avatar-web-template | 智能客服 / H5 / 大屏，想快速拿链接 |
| 数字人直播 | 营销带货直播间（商品 / 分镜 / 脚本） | avatar-live-streaming | 虚拟主播、带货直播场景 |
| 接 SDK 自建 | 真正的前端 / 客户端工程项目 | avatar-brainstorming → avatar-executing | 需要定制 UI、深度集成、控制交互细节 |

判定规则：
- 用户信号明确偏向某一路径（如"用模板""要个链接" / "直播""带货""虚拟主播" / "接 SDK""自己写前端""要个工程"）→ 直接路由，不必再问
- 信号不明确（如仅"构建一个虚拟人对话项目"）→ 先 `AskUserQuestion` 让用户在上述路径中选择，再路由
- **不要**在澄清中列出尚未支持的交付形态，只呈现当前可交付的路径

---

## 方法论增强（横切能力，非意图路由目标）

上表是"用户意图 → 业务 skill"的路由。另有一类跨领域方法论 skill（`skills/shared/`），
不是用户开口要的东西，而是**在执行编码/多任务时自动应用**。路由到实施类目标
（brainstorming/executing 等）时，若命中以下场景，一并提示应用对应方法论：

| 场景信号 | 应用方法论（skills/shared/） | 落地位置 |
|----------|------------------------------|----------|
| 要写可单测的业务逻辑/函数/模块、或修逻辑 bug | test-driven-development（先写失败测试再实现） | avatar-executing Step 3 |
| 手头有多个**互不依赖、不写同一文件**的任务 | dispatching-parallel-agents（并行分发子 agent） | avatar-planning 标注 + avatar-executing Step 3 |

说明：这两个是**增强**不是门禁——SDK 真机交互无法单测的部分不套 TDD（走
avatar-verification 运行时验证）；有依赖的任务不并行（仍串行）。

---

## 关键约束

### 优先级规则（HARD-GATE）

故障排查 > 权限/网络问题 > 配置调整 > 首次接入/功能扩展

多个信号命中时，**必须**按上述优先级选择路由目标。

### 置信度阈值（HARD-GATE）

- **> 0.8**：直接路由
- **0.5 - 0.8**：询问用户确认
- **< 0.5**：回退到 avatar-brainstorming 完整流程

### Red Flags

- 工程扫描结果与用户描述矛盾（如称"已集成"但扫描无 SDK）→ 以扫描结果为准并提示用户
- 同时命中故障排查与配置调整 → 优先故障排查
- 需求模糊且平台未知 → 不要猜测，回退完整流程澄清

### 其他注意事项

- **工程扫描**：利用缓存避免重复扫描，扫描结果作为路由决策依据
- **用户体验**：明确问题快速路由，模糊需求走完整流程，避免过度询问

### 执行原则（HARD-GATE：路由到实施类目标后适用）

- **第一条消息就走 skill**：avatar 相关需求一进来就调用本入口做路由，**不要**先用通用知识
  抛技术选型问题（如 Unity / Three.js / 2D-3D）。本平台走讯飞官方能力，通用选型问答是跑偏。
- **主动执行，最小化用户手动操作**：涉及命令行工具的步骤由 Claude 直接用 Bash/PowerShell 执行，
  **不要**让用户在输入框自己输命令（`! ...`）。跑命令、切目录、打开浏览器都是 Claude 的工作。
- **浏览器交互分工**：需要浏览器的命令（登录、create、publish）直接执行且**默认不加 `--no-browser`**，
  让浏览器自动弹出；用户只负责浏览器里的人类动作（扫码、测试对话）。**切勿**只贴链接让用户自己打开。
- **HARD-GATE 前置校验要提前**：如模板路径要求 appType=2，应在 create **之前**用 `list-apps` 校验，
  别等到 create 被门禁拦下才发现。
- **阻塞时给明确选项**：遇到无法自动解决的阻塞（如需用户订阅新应用），立刻给出"路径 A / 路径 B"
  式的可选方案 + 各自 trade-off + 相关链接，而不是只报告问题。
- **平台端点由工具持有，模型无权补全**：Web SDK 的唯一服务地址是
  `wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`。控制台只能通过
  `python "${CLAUDE_PLUGIN_ROOT}/tools/xfyun_common.py" projects` 打开。不得询问用户 `WS_URL`，
  不得根据域名规律拼接或手工执行其他控制台 URL。
- **阻断必须继续确定性流程**：`web_delivery.py` 返回退出码 2 时，读取 JSON 的 `next_action` 并立即执行；
  `blocked_missing_credentials` 必须进入 `avatar-credentials`，不能退回通用知识回答或让用户提供 WS 地址。
- **门禁与上报由状态机负责**：退出码 2/3 保持 workflow 为 `in_progress` 并进行非终态门禁上报；
  只有退出码 0 / `ready_to_deliver` 才完成上报。模型不得直接调用 Reporter 改写结论。
- **⚠️ SDK 自建工程按 workflow_mode 分流（Android/Web）**：
  - `quick`：`avatar-brainstorming` 形成内存实施摘要后**直接**调用 `avatar-executing`，主 agent 依
    Playbook 实现；不生成 design-spec/implementation-plan，不跑 writer-reviewer 循环。
  - `strict`：完整走 `avatar-brainstorming` → `avatar-planning` → `avatar-executing`，保留
    spec/plan/code 评审与完整报告。
  - **两种模式都不允许**跳过 `avatar-executing` 的真实 Playbook：主 agent 凭记忆手写代码会用错 API
    （Android 的 `createStreamPlayer`/`sendText` 等不存在，Web 会踩 bitrate 陷阱、前端硬编码
    apiSecret），导致编译失败、黑屏或构建 20+ 分钟。
  - Web SDK 自建只能执行
    `python "${CLAUDE_PLUGIN_ROOT}/tools/web_delivery.py" run --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" --interaction "<text|voice|audio>"`；
    状态机固定完成完整凭据、canonical auth 模块、SDK、服务状态和服务端签名校验。浏览器证据产生后重复同一命令，内部才运行最终 gate 和完成上报。
  - **Web 骨架与状态机边界**：`avatar-executing` 可在凭据和 SDK 尚未就绪时先创建最小
    `server.js` / `public/app.js` / `package.json` 骨架。`web_delivery.py` 不是代码生成器，且第一项检查就是
    `server.js` 是否已存在；不存在时返回 `blocked_server_lifecycle` + `server_js_missing`。骨架存在后才运行
    `web_delivery.py run` 编排凭据、canonical auth、SDK、服务和门禁；用
    `web_delivery.py status --project "<project>"` 读取持久化状态。
  - Web 前端固定调用 `GET /api/avatar-auth -> {signedUrl,timestamp}` 与
    `GET /api/config -> {appId,sceneId,avatarId,vcn,wsUrl}`，然后
    `setApiInfo({signedUrl, appId, sceneId})`。`apiKey/apiSecret` 只保存在 Node 服务端，禁止传入前端。
  - 退出码 2/3 都不得完成，只有退出码 0 / `ready_to_deliver` 才能交付。禁止手写/读取 `.env`、手写运行证据、全局结束 Node、直接运行 `web_sdk_gate.py` 或 Reporter complete；端口只使用工具返回的实际 URL。
  - Android 构建必须同时遵循 `../shared/android-gradle-stability.md`：串行构建、在线预热、
    `--offline` 复验，超时先查原进程而不是重复执行。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/routing-rules.md` | **路由规则唯一权威来源**：意图优先级、关键词/指标映射、边界规则 |
| `references/routing-flow.md` | 三步路由流程的完整 JavaScript 实现 |
| `references/route-targets.md` | 各路由目标的适用场景、输入、输出 |
| `references/examples.md` | 各置信度场景的完整路由示例 |
| `../shared/delivery-modes.md` | `workflow_mode: quick\|strict` 的选择、必问门禁、Token 纪律 |
| `../shared/android-gradle-stability.md` | Android Gradle 镜像、内存/并发、缓存锁与超时处理 |

本文件的"决策分支"表只是快速索引；出现分歧时以 `references/routing-rules.md` 为准。

---

## 输出格式

### 成功路由
```yaml
status: "routed"
target: "avatar-troubleshoot"
confidence: 0.95
reason: "明确的错误码和异常行为"
```

### 需要确认
```yaml
status: "needs_confirmation"
suggested_target: "avatar-config-authoring"
confidence: 0.75
question: "检测到您想调整虚拟人分辨率，是否需要我帮您修改配置？"
```

### 回退到完整流程
```yaml
status: "fallback_to_full_workflow"
target: "avatar-brainstorming"
reason: "需求不明确，需要完整的澄清流程"
```

---

## 相关技能

- `avatar-brainstorming`: 完整工作流入口
- `avatar-troubleshoot`: 故障排查
- `avatar-config-authoring`: 配置调整
- `avatar-permissions-setup`: 权限配置
- `avatar-network-debug`: 网络诊断
