---
name: avatar-executing
description: 虚拟人集成任务的执行实现阶段（三阶段工作流第三阶段）
---

# avatar-executing: 执行实现

## 定位

三阶段工作流的 **Phase 3: 执行实现**，负责按计划逐步实现代码，并进行质量评审和验证。

先读 `../avatar-shared/delivery-modes.md`，接收上游 `workflow_mode: quick | strict`。

- `quick`：主 agent 依 Playbook 直接实现，不派发 writer/reviewer，不生成过程文档。
- `strict`：使用 writer/reviewer 循环，生成完整报告。

模式不明确时返回上游询问用户，不能默认 quick，也不能边实现边补模式。

## 共同前置门禁

- 需求边界、启用与排除能力明确。
- 首次自建或多能力扩展已有用户选择的 `workflow_mode`；没有选择时停止。
- 新增语音、麦克风权限或录音代码前，已有用户对语音能力和交互形态的明确确认。
- 凭据、sceneId 发布状态、资源授权、SDK、网络和工具链已验证。
- Android/Web 首次接入全文读取对应真实 Playbook。
- Android 构建按 `../avatar-shared/android-gradle-stability.md` 执行。

## 触发条件 / 调用时机

- 已完成 `avatar-planning`，产出实现计划文档 (`implementation-plan.md`)
- preflight 环境验证已通过
- 需要将计划落地为实际代码并验证

## 输入

- 实现计划文档路径 (`implementation-plan.md`)
- 平台类型 (`web` | `android` | `ios`)
- 任务类型 (`first_integration` | `feature_extension` | `config_adjustment`)

## 输出

- 实现的代码文件
- 验证结果报告
- 下一步：可选的 Git 收尾（手动提交，暂无独立 skill）

---

## 工作流程概览

```
Step 1: 读取实现计划
Step 2: 确定执行模式（通用 vs 领域适配）
Step 3: 逐步执行实现
  - 调用 code-writer / avatar-code-writer
  - 调用 code-reviewer / avatar-code-reviewer
  - 验证每步结果
Step 4: 完整性验证
Step 5: 生成验证报告

→ 输出: 实现代码 + 验证报告
→ 可选: Git 收尾（手动提交）
```

| Step | 目标 | 详见 |
|------|------|------|
| 1 | 读取并解析实现计划、检查前置条件 | 本文件 Step 1 |
| 2 | 确定执行模式 | 本文件 Step 2 |
| 3 | 逐步执行、生成/评审/验证 | references/execution-loop.md, avatar-code-writer.md, avatar-code-reviewer.md, verification.md |
| 4 | 端到端 / 异常 / 性能验证 | references/verification.md |
| 5 | 生成验证报告 | references/output-formats.md |

---

## Step 0: 前置验证与反幻觉检查

**目标**：防止基于"常识推理"而非"实际代码/文档"的幻觉问题。

### 0.1 加载反幻觉清单

```bash
Read references/anti-hallucination-checklist.md
```

**强制执行的核心原则**：
- ❌ 禁止假设 API 端点、数据结构、文件内容
- ✅ 必须 Read → Understand → Use
- ✅ 检查 exit code，验证副作用
- ✅ 不确定时说"我不知道"，而非编造

### 0.2 前置门禁检查

**必要条件**：
- [ ] 需求边界明确（启用/排除能力已确认）
- [ ] 工作模式已选择（quick/strict，不能默认或猜测）
- [ ] 权限变更已告知（新增语音/麦克风权限需用户确认）

**违规检测**：
- 如果说"我假设使用 quick 模式" → **STOP，返回询问**
- 如果说"这个 API 应该是..." → **STOP，先 Read 源码**

---

## Step 1: 读取实现计划

**【反幻觉检查点 A】：文件读取前**

### 1.1 解析计划文档

**提取信息**:
```yaml
steps:
  - id: "step1"
    title: "SDK 安装与引入"
    target: "集成 SDK 文件"
    operations: [...]
    verification: [...]

platform: web | android | ios
estimated_time: "2-4 hours"
risks: [...]
```

### 1.2 检查前置条件

**必需检查**:
```yaml
checks:
  - design_spec_exists: true
  - plan_reviewed: true
  - environment_verified: true  # preflight 已通过
  - dependencies_ready: true
```

**失败处理**: 提示缺失项，返回到对应阶段

---

## Step 2: 确定执行模式

### 2.0 SDK 自建工程强制前置检查（HARD-GATE：Web 与 Android）

**触发条件**: `platform in ("web","android")` 且涉及 SDK 集成（非纯配置调整）

**⚠️ 强制执行规则（不可跳过）**:

1. **第一步：主 agent 必须先 Read playbook 全文**
   - Android: `Read <plugin-root>/skills/avatar-executing/references/android-sdk-build-playbook.md`
   - Web: `Read <plugin-root>/skills/avatar-executing/references/web-sdk-build-playbook.md`
   - **不允许**跳过直接手写代码，**不允许**用"我反编译过AAR"作为豁免理由

2. **Web SDK 必须执行确定性交付状态机，不接受模型自行编排**
   - 运行状态机前主 agent 必须先 Read：`../avatar-credentials/SKILL.md`、`../avatar-artifact-download/SKILL.md`、`../avatar-network-debug/references/auth-verification.md`；这些真实 Read 才会形成对应 invocation，不能把状态机内部 Python 调用冒充 Skill invocation。
   - 唯一入口：
     `python "<plugin-root>/tools/web_delivery.py" run --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" --interaction "<text|voice|audio>"`
   - 首次运行固定执行：平台获取完整凭据并安全写入 `.env` → 校验字段 → 安装哈希校验的 `xfyun-auth.mjs` → 下载/校验 SDK → 启动服务并记录实际端口 → 校验 `/api/config` 和 `/api/avatar-auth` 使用当前完整 Key/Secret → 打开浏览器。
   - `WS_URL` 是平台常量，只能是 `wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`。不得询问用户、
     不得接受其他 host/path、不得让代码从模型回复中读取地址；控制台只运行
     `python "<plugin-root>/tools/xfyun_common.py" projects` 打开。
   - 浏览器产生真实运行证据后再次运行**同一命令**；状态机才会执行最终 gate，且只有 `ready_to_deliver` 才调用 telemetry complete。
   - 退出码 2 表示确定性阻塞，3 表示等待浏览器证据，0 才表示可交付。2/3 都保持同一 workflow 进行中。
   - 退出码 2 时必须解析 stdout JSON：若状态为 `blocked_missing_credentials`，立即读取并执行
     `next_action.commands`，转入 `avatar-credentials`。禁止改成自由文本指导、禁止自行补 URL、禁止把终端命令甩给用户。
   - **非终态门禁上报**由 `web_delivery.py` 自动调用 `telemetry.report_gate`，记录 gate/status/issues 但不结束
     workflow；退出码 3 同样上报等待验证状态。模型不得手工调用 `report_gate`、`report_fail` 或 `report_complete`。
   - 禁止绕过状态机直接手写/读取 `.env`、直接运行 `web_sdk_gate.py` 或 `telemetry.py complete`；禁止手写 `.runtime/web-runtime-evidence.json`；禁止杀掉全部 Node 进程。PID/端口只作为当前服务状态和实际访问 URL，不是身份硬门禁。
   - `server.js` 不得手写 HMAC 或 signed URL。必须挂载脚本生成的 `xfyun-auth.mjs` 导出的 `avatarConfigHandler` 和 `avatarAuthHandler`；其哈希不匹配时停止。
   - 读取工具确认的真实 `index.d.ts`，导入必须使用 `module.default`；逐项确认 `setApiInfo`、`setGlobalParams`、`start` 和目标驱动方法。
   - 状态机内部只通过 `write_env_safe.py --profile web-sdk` 获取完整凭据；脱敏输出不得拼回 `.env`，不得回显密钥或解码后的 Authorization。
   - 服务端签名先读 `../avatar-network-debug/references/auth-verification.md`，必须包含 request-line 和 `headers="host date request-line"`。
   - Playwright/浏览器测试必须生成真实 `connected`、`stream_start`、首帧和目标交互证据，不得手写通过值。

3. **Android 必须用 playbook §6 完整模板，禁止自己拼 API**
   - MainActivity: 必须基于 `references/android-mainactivity-template.java` 修改（140+ 行真实可跑模板）
   - build.gradle: 必须用 playbook §6.3 模板（jniLibs.srcDirs/okhttp/gson依赖/AGP 8.1.4）
   - settings.gradle: 必须用 `templates/android-build-template/settings.gradle.template`
     （镜像顺序：阿里云 → 腾讯云 → 华为云 → 官方兜底）
   - gradle.properties: 必须用 `templates/android-build-template/gradle.properties`
     （Xmx1280m、parallel=false、workers.max=2）
   - 构建执行、超时处理和离线验收必须遵循 `../avatar-shared/android-gradle-stability.md`：
     同一工程同时只跑一个 Gradle 调用；命令超时先检查原进程再决定等待，禁止立即重跑；
     冷缓存先在线预热再 `--offline` 复验；禁止无依据 `clean --refresh-dependencies`、
     禁止删除全局 Gradle 缓存、禁止杀死全部 Java 进程。

4. **Android API 黑名单自动检测（写完代码后必须 grep）**
   ```bash
   # 这些 API 在真实 SDK 中不存在，命中即报错
   grep -r "createStreamPlayer\|sendText\|onNlpResult\|onAsrResult\|onAvatarReady\|writeAudioFrame\|startAudioInteract\|setApiKey(" <工程目录>
   ```
   如果 grep 有输出，说明用了错误 API，必须按 playbook §1 真实签名改写

5. **Gradle Wrapper 必须用预置模板（见 §2.0.2），禁止在线下载**

**违规后果（Web）**: 遗漏 bitrate → `must be ≥ 200`；只配顶层 stream.bitrate → SDK /1024 变成 1；前端硬编码 apiSecret → 泄露。
**违规后果（Android）**: 照 avatar-integration-guides/android.md 简化 API 写 → `sendText`/`createStreamPlayer`/`onNlpResult` 等不存在 → 编译失败或运行崩溃；`--no-daemon` → 编译 20+ 分钟；未 setRenderArea → 黑屏。

#### 2.0.1 门禁不是"读一遍"，是四个可核验动作（防自我豁免）

上面的 `if (!playbook_followed) throw` 是**伪代码，没有约束力**。历史事故正是：主 agent"读了"
playbook，却用"我自己 javap 能拿到真 API"说服自己绕过，且**派发给写代码的子 agent 时没带 playbook**
——子 agent 不共享主 agent 上下文，主 agent 读了≠子 agent 读了。所以门禁落地为四个**必须留痕**的动作：

1. **主 agent 先 Read playbook 全文**（Android=`android-sdk-build-playbook.md`，Web=`web-sdk-build-playbook.md`）。
2. **派发 avatar-code-writer 时，prompt 里必须带 playbook 全路径 + 模板路径，并明确要求它"先 Read 再写"**。
   ❌ 不允许只把主 agent 手搓的 api-notes 丢给子 agent 当唯一依据。
3. **派发 avatar-code-reviewer 时，prompt 同样带 playbook**，并要求按 `avatar-code-reviewer.md` 的
   Android C1-C8 清单逐条核对。
4. **代码写完 grep 失真 API 黑名单**（`createStreamPlayer|sendText|onNlpResult|onAsrResult|onAvatarReady|writeAudioFrame|startAudioInteract|setApiKey(`），
   命中即打回。这一步是客观检查，不能靠"我觉得写对了"跳过。

> **自我豁免检测**：如果你正打算用"这次情况特殊/我反编译过了/时间紧"来跳过上述任一动作，
> 停下——这正是历史踩坑的心理路径。javap 反编译是**补充**核对手段，不是**替代** playbook 的理由。

### 2.1 模式选择规则

**通用模式** (`code-writer` + `code-reviewer`):
- 纯配置调整
- 不涉及虚拟人 SDK 特有逻辑
- 标准前端/移动端开发
- 适用: 修改分辨率/码率、UI 布局调整、通用业务逻辑

**领域适配模式** (`avatar-code-writer` + `avatar-code-reviewer`):
- 涉及虚拟人 SDK 集成 / WebSocket 鉴权 / 播放器配置 / 录音器 / 事件处理
- 适用: SDK 初始化、文本驱动/交互、语音交互、透明背景配置、错误处理

**决策原则**: 不确定时使用领域适配模式（更安全）。

---

## 决策分支（场景 → 应读哪个 reference）

**⚠️ 优先级规则**: Web / Android SDK 自建工程必须最先读取对应 playbook，再读其他 reference。

| 场景 | 应读 reference | 优先级 |
|------|----------------|--------|
| **构建 Web SDK 自建工程（web 平台 first_integration）** | **references/web-sdk-build-playbook.md（HARD-GATE，必读必守，最高优先级）** | **P0 - 强制首读** |
| **构建 Android SDK 自建工程（android 平台 first_integration）** | **references/android-sdk-build-playbook.md（HARD-GATE，真实 API 全表+性能配置+模板，最高优先级）** | **P0 - 强制首读** |
| 编写 Step 3 主执行循环逻辑 | references/execution-loop.md | P1 |
| 领域适配代码生成（鉴权/播放器/事件/平台最佳实践） | references/avatar-code-writer.md | P1 |
| 领域适配代码评审（专有陷阱/配置/资源/错误处理） | references/avatar-code-reviewer.md | P1 |
| 步骤验证 / 端到端 / 异常 / 性能验证方法 | references/verification.md | P2 |
| 生成验证报告、成功/部分/失败输出格式 | references/output-formats.md | P2 |

### ⚠️ Web 平台强制流程（HARD-GATE）

**判定条件**:
```javascript
if (platform === 'web' &&
    (taskType === 'first_integration' ||
     涉及 SDK 初始化/setGlobalParams/驱动/语音)) {
  // 必须执行以下流程
}
```

**强制执行**:
1. **第一步**: 读取 `references/web-sdk-build-playbook.md` 全文（197 行）
2. **第二步**: 检查 §0 bitrate/1024 陷阱和 SDK 真实组装逻辑
3. **第三步**: 按 §3 字段锁定表逐字段生成配置（不允许遗漏或自由发挥）
4. **第四步**: 按 §2 六步构建流程生成代码（每步带验证）
5. **第五步**: 执行 §5 端到端验证清单

**具体要求**:
- 采用 playbook §1 规定的"Node 后端签名 + 静态前端"架构（禁止前端硬编码 apiSecret）
- `avatar.stream` **必须手写**并用真实 kbps 值（如 `bitrate: 2000`），避免 SDK 的 /1024 陷阱
- 所有参数必须对照 §3 锁定表，不允许遗漏 bitrate/framerate/protocol 等
- **不允许**"先生成、跑起来看报错、再逐个改字段"的试错式开发

**违规检测**:
```bash
# 生成代码后必须通过以下检查
grep -q "bitrate.*2000" app.js || echo "[ERROR] 缺少 bitrate 参数"
grep -q "avatar.*stream" app.js || echo "[ERROR] 未手写 avatar.stream"
grep -q "apiSecret" public/ && echo "[ERROR] 前端泄露 apiSecret"
```

违反此门槛导致的 bitrate/protocol/apiSecret 类问题属于**可预防缺陷**，不得出现在交付代码中。

### ⚠️ Android 平台强制流程（HARD-GATE）

**判定条件**:
```javascript
if (platform === 'android' &&
    (taskType === 'first_integration' || 涉及 SDK 初始化/setGlobalParams/驱动/语音)) {
  // 必须执行以下流程
}
```

**强制执行**:
1. **第一步**: 读取 `references/android-sdk-build-playbook.md` 全文（真实 API 全表 + 六步 + 字段锁定 + 性能 + 模板）
2. **第二步**: 客户端 API 严格按 §1 真实签名生成，**禁止**照 `avatar-integration-guides/android.md` 的简化 API 或凭记忆臆造
3. **第三步**: 按 §3 写入 gradle.properties 六项性能配置；编译用 `gradlew`（**严禁 `--no-daemon`**）
4. **第四步**: 按 §2 六步构建流程生成（下载AAR→骨架→权限/gradle→凭据→MainActivity→四功能+编译真机）
5. **第五步**: 执行 §5 一次跑通验证清单（含知识库命中验证）

**具体要求**:
- 初始化 `AvatarPlatform.initialize(ctx, config, IInitListener)` 3 参，成功 code="0"
- 监听器用 **`IAvatarListener`**（onResult/onEvent/onError），nlp/asr 文本从 onResult 的 **extra JSON** 取
- 交互 `writeText(text, TextParams.setNlp(true))`；播报 `writeText(text)`；语音 `setAudioRecorder(recorder, audioParams)`
- 渲染 `createPlayer(ctx,"xrtc")` + `setRenderArea(容器)`（否则黑屏）
- .so 只靠 AAR，不手动放 webrtc .so（否则 duplicate 冲突）
- **不允许**"先生成、跑起来看报错、再逐个改字段"的试错式开发

**违规检测**:
```bash
# 生成 MainActivity 后必须通过以下检查（出现即错，这些 API 在真实 SDK 不存在）
grep -qE "sendText|createStreamPlayer|onNlpResult|onAsrResult|onAvatarReady|writeAudioFrame|startAudioInteract" MainActivity.java && echo "[ERROR] 使用了不存在的简化文档 API，必须改真实 API"
grep -q "IAvatarListener" MainActivity.java || echo "[ERROR] 未使用真实监听器 IAvatarListener"
grep -q "setRenderArea" MainActivity.java || echo "[ERROR] 未用 setRenderArea 挂载渲染面（会黑屏）"
grep -q "org.gradle.daemon=true" gradle.properties || echo "[ERROR] 缺 gradle 性能配置，编译会极慢"
```

违反此门槛导致的 API 不存在/黑屏/编译超慢类问题属于**可预防缺陷**，不得出现在交付代码中。

---

## 关键约束 / HARD-GATE / Red Flags

**HARD-GATE（前置门槛，未满足禁止进入 Step 3）**:
- `workflow_mode` 已由用户选择（首次自建或多能力扩展）；未选择时停止
- `strict` 模式：design_spec 必须存在、实现计划必须已评审
- `quick` 模式：实施摘要边界（`features` / `excluded`）已确认；不要求设计或计划文件存在
- 新增语音、麦克风权限或录音代码前，已有用户对语音能力和交互形态的明确确认
- preflight 环境验证必须已通过
- 依赖必须就绪

**Red Flags（领域适配模式必查的高危陷阱）**:
- **用户未选择语音却加入麦克风权限、`RECORD_AUDIO` 或录音代码 → 违反语音门禁，必须回退确认**
- **用户未选择交付模式却开始首次自建或多能力扩展 → 违反交付模式门禁**
- **快速模式仍生成 design-spec/implementation-plan 或派发常规 writer/reviewer → 违反 quick 约定**
- 未发布/未授权资源进入运行配置
- **[Web] 只配顶层 `stream.bitrate:2000` 而不手写 `avatar.stream` → SDK 会 /1024 变成 1，报 `must be ≥ 200`。必须按 playbook §3 手写 `avatar.stream` 用真实 kbps 值**
- **[Web] 前端 JS 硬编码 apiSecret → 安全泄露。必须用 Node 后端签名 + signedUrl（playbook §1）**
- **[Web] SDK 缺失、只通过 HTTP/config 检查或没有浏览器事件证据却标记完成 → 必须保持 `blocked_missing_sdk` / `needs_runtime_verification`，禁止 Reporter complete**
- **[Web] 手工创建 `.env`、读取并回显凭据、全局结束 Node、手写 signed URL 或在浏览器证据前直接跑最终 gate → 必须停止并改用 `web_delivery.py run`**
- **[Web] 使用 `setServerUrl()`、`getPlayer()` 或把 `AvatarPlatform` 当具名导出 → 真实 SDK 不支持，必须按 `index.d.ts` 修正**
- 透明背景仅配置一处 → 必须 `stream.setAlpha` 与播放器 `setBgAlpha` 两处都配
- 透明背景使用非 XRTC 协议（WebRTC/等）→ 无效，仅 XRTC 支持
- 录音器采样率 ≠ 16000 → 虚拟人 SDK 要求 16000
- 缺少 `error` 事件监听 → 必须监听 connected / error / disconnected
- 资源未释放（onDestroy 未 stop + destroy）→ 内存泄漏
- 录音中直接 destroy → 必须先 stopRecord 再 destroy
- SDK 启动无 try/catch 错误码处理 → 必须捕获并按错误码处理

**执行约束**:
- 涉及 SDK 的步骤优先使用领域适配模式
- 每步完成后立即验证：编译验证 → 运行验证 → 功能验证
- 验证失败先分析原因，再决定修复/跳过/中止

**方法论增强（跨领域，见 skills/avatar-shared/）**:
- **TDD**：生成可单测的业务逻辑/函数/模块时，先写会失败的测试再写实现
  （`skills/avatar-shared/avatar-test-driven-development/`）。SDK 真机交互部分（首帧/播放/录音/连通）
  无法单测，仍走 Step 4 运行时验证，不套 TDD。
- **并行分发**：Step 3 逐步执行默认串行（step 间通常有依赖）。当计划中某一批 step
  被标注为**互不依赖、不写同一文件**时，用并行分发同时派发 writer 加速
  （`skills/avatar-shared/avatar-dispatching-parallel-agents/`）；有依赖的仍串行。

---

## 决策流程

### 验证失败时的决策

```
验证失败
    ↓
分析失败原因
    ↓
┌─────────────┬─────────────┬─────────────┐
│ 配置错误    │ 代码缺陷    │ 环境问题    │
└─────────────┴─────────────┴─────────────┘
    ↓              ↓              ↓
修复配置      重新生成代码    提示用户修复
    ↓              ↓              ↓
重新验证      重新评审        等待用户操作
    ↓              ↓              ↓
    └──────────────┴──────────────┘
                   ↓
            验证通过 → 继续
```

### 代码评审失败时的决策

```
评审发现问题
    ↓
┌──────────────┬──────────────┐
│ Critical/High│ Medium/Low   │
└──────────────┴──────────────┘
    ↓              ↓
必须修复        记录到报告
    ↓              ↓
重新生成        继续执行
    ↓              ↓
重新评审        最终报告中说明
```

---

## references/ 索引表

| 文件 | 内容 |
|------|------|
| references/anti-hallucination-checklist.md | **【贯穿全流程】反幻觉验证清单：API调用/数据访问/文件编辑/工具执行/链接引用/子agent派发的强制验证规则** |
| references/web-sdk-build-playbook.md | **【HARD-GATE】Web SDK 自建工程唯一权威流程：架构/六步/字段锁定表/bitrate 陷阱/验证清单** |
| references/android-sdk-build-playbook.md | **【HARD-GATE】Android SDK 自建工程唯一权威流程：真实API全表/六步/字段锁定表/性能配置/模板/黑名单检测** |
| references/execution-loop.md | Step 3.1 执行循环完整代码（writer/reviewer 选择、应用变更、验证） |
| references/avatar-code-writer.md | Step 3.2 avatar-code-writer 领域适配器 5 大能力代码示例 |
| references/avatar-code-reviewer.md | Step 3.3 avatar-code-reviewer 领域适配器专有检查（陷阱/配置/资源/错误处理，含反例） |
| references/verification.md | Step 3.4 步骤验证 + Step 4 端到端/异常/性能验证的命令与清单 |
| references/output-formats.md | Step 5 验证报告结构模板 + 成功/部分成功/失败输出格式 |

---

## 验证清单

- [ ] HARD-GATE 前置门槛全部满足
- [ ] 每个 step 均完成生成 → 评审 → 验证
- [ ] 编译验证通过
- [ ] 功能验证通过（SDK 初始化 / 连接 / 播放 / 文本驱动 等按需）
- [ ] Red Flags 全部排查无遗漏
- [ ] 性能指标达标（首帧 < 3s、帧率 >= 20fps、播报延迟 < 500ms 等）
- [ ] 验证报告已生成

## 交接协议

- 成功: 输出实现代码 + 验证报告，可选的 Git 收尾（手动提交）
- 部分成功: 报告已完成/失败步骤及修复建议，等待用户决策
- 失败: 报告失败步骤、错误码与修复建议，必要时回退到 preflight / planning

---

## 相关技能

- `avatar-planning`: 上游技能（提供实现计划）
- `code-writer` (agent): 通用模式代码生成
- `code-reviewer` (agent): 通用模式代码评审
- `avatar-code-writer` (agent): 领域适配代码生成
- `avatar-code-reviewer` (agent): 领域适配代码评审
- Git 收尾：可选的手动步骤（暂无独立 skill，按需手动提交）

---

## 9. 预置 Android Gradle 环境模板（立即创建任务）

**问题**: gradle-wrapper.jar 从国外下载慢且易失败，导致首次构建卡住或超时。

**解决方案**: 预置完整 Gradle 环境到 `skills/avatar-executing/templates/android-build-template/`，包含：
- gradle-wrapper.jar（从阿里云镜像预下载）
- gradle-wrapper.properties（distributionUrl 指向腾讯云镜像）
- gradle.properties（六项性能配置：daemon/parallel/caching/configureondemand/jvmargs/useAndroidX）
- settings.gradle.template（阿里云 maven 镜像）
- build.gradle.template（AGP 8.1.4，适配 JDK 17）
- gradlew / gradlew.bat（wrapper 脚本）
- .gitignore（排除 build/、local.properties、credentials.json）

**使用方式**（avatar-code-writer 生成安卓工程时）:
1. 复制 `android-build-template/*` 到目标工程根目录
2. 替换 settings.gradle.template 和 build.gradle.template 中的占位符（项目名、包名）
3. 创建 app/ 目录、MainActivity、layout、AndroidManifest.xml
4. 直接运行 `gradlew assembleDebug`，无需等待 wrapper 下载

**立即执行**: 见 `scripts/setup-android-build-template.sh`（需手动创建该脚本并执行一次）
