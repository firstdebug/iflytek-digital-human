# 交付模式（workflow_mode）

虚拟人 SDK 自建和大型功能扩展使用两种交付模式。模式只改变过程文档、确认次数和 agent 评审成本，
**不改变**凭据、安全、真实 SDK API、构建和运行验证门禁。

> 字段名固定为 `workflow_mode`。不要用 `delivery_mode` 表示 quick/strict —— 该字段在本技能包中
> 已用于表示交付形态（SDK 自建 / 官方模板 / 直播），两者含义不同，混用会导致路由错误。

## 模式选择

首次 SDK 自建或多能力扩展时**必须先问一次**；没有得到用户选择前不得默认进入 `quick`，也不得开始写代码。
用 `平台交互提问` 提问，选项如下：

| 选项 | 含义 |
|------|------|
| 快速交付（推荐） | 不生成设计/计划过程文档，主 agent 直接实现，不启用 writer-reviewer 循环 |
| 严格流程 | 生成完整设计与实施计划，并执行 spec/plan/code 评审；适合审计、多人交接或高风险生产改造 |

选择规则：

- 用户说"快速、少文档、直接做、先跑起来、不要 reviewer、节省 token"→ `quick`，不重复询问。
- 用户说"完整设计、严格流程、完整文档、严格评审、审计、多人交接"→ `strict`，不重复询问。
- 已有项目的普通单一配置或修复默认 `quick`，无需提问；但新增会改变权限、采集用户输入或扩大用户
  能力面的功能必须单独确认（见下方语音门禁）。
- 首次 SDK 自建或多能力扩展未表态时询问一次，推荐 `quick`；**用户未回答时停止**，不用"推荐"代替选择。
- 新增语音识别、语音交互、麦克风权限、摄像头、直播、知识库写操作或外部模型绑定时，除交付模式外
  还要确认对应能力边界；用户只说"做一个项目"不能推断需要这些能力。

## 必问门禁

开始实现前按需问最少问题：

1. **交付模式**：首次 SDK 自建、从零构建或多能力扩展必须让用户选择 `quick` 或 `strict`。
2. **语音能力**：任何新增语音识别、语音问答、录音或 `RECORD_AUDIO` 权限前，必须问用户是否确认
   加入语音，以及交互形态（按住说话 / 点击开始停止 / 自动 VAD / 全双工）。

只有用户在当前任务中明确回答后才继续。模糊表达如"先做吧""看着办"不能替代上述两个选择。
不因任务看起来复杂而擅自切换模式；认为应升级时说明理由并让用户决定。

## 快速交付 quick

```yaml
workflow_mode: quick
process_documents: false
writer_reviewer_loop: false
approval_pauses: 1
implementation_owner: main_agent
```

流程：

1. 扫描已有工程并确认平台。
2. 用一次紧凑提问补齐会改变实现路径的信息。
3. 在当前上下文维护不超过 12 行的实施摘要，不创建 `design-spec.md` 或 `implementation-plan.md`。
4. 执行针对性 preflight 和资源验证。
5. 主 agent 全文读取对应平台 Playbook，直接实现并运行客观扫描、测试、构建和真机验证。
6. 用简短最终结果交付；默认不创建过程型 `verification-report.md`。用户需要的 README、部署说明或
   产品文档不属于过程文档，可以生成。

快速实施摘要至少包含：

```yaml
workflow_mode: quick
platform: web | android | ios
project_path: <path>
features: [明确启用的能力]
excluded: [明确不做的能力]
protocol_and_background: <value>
resources: <复用/新建策略，不含密钥>
acceptance: [构建、运行、核心交互]
```

快速模式默认不调用 `spec-reviewer`、`plan-writer`、`plan-reviewer`、`avatar-code-writer` 或
`avatar-code-reviewer`。主 agent 不需要为了模拟这些角色而生成等量文本。

只有出现以下客观信号时，才允许增加一次针对性 reviewer；不自动恢复整套三阶段：

- 当前 SDK/AAR 签名与 Playbook 不一致。
- 静态扫描命中失真 API、密钥泄漏或关键生命周期缺陷。
- 同一阻塞问题修复两次后仍失败。
- 用户明确要求独立评审。

## 严格流程 strict

```yaml
workflow_mode: strict
process_documents: true
writer_reviewer_loop: true
approval_pauses: 3
implementation_owner: staged_agents
```

沿用完整流程：

1. `avatar-brainstorming` 生成并评审设计规格。
2. `avatar-planning` 生成并评审实施计划。
3. `avatar-executing` 使用 writer/reviewer 循环实现。
4. `avatar-verification` 生成完整验证报告。

严格模式适合用户明确需要审计留痕、多人/多团队交接、多平台同步实施、生产安全架构变更或正式方案评审。

## 两种模式都不能跳过

- 明确平台、功能范围和明确排除项，不能自行加入语音、动作、透明背景等能力。
- 验证 appId/sceneId 归属、发布状态和资源授权；无效场景不能进入运行配置。
- Android/Web 首次接入全文读取 `avatar-executing` 对应真实 Playbook。
- Android 构建遵循 `android-gradle-stability.md`：串行、在线预热、`--offline` 复验。
- 密钥不进入源码、对话、日志或版本库；生产客户端不长期保存 apiSecret。
- SDK 产物、工具链、网络和依赖满足目标平台要求。
- 运行静态缺陷扫描、必要测试、构建和目标功能验证。
- 无真机或外部平台阻塞时如实标记未验证项，不能宣称完整交付通过。

## Token 纪律

- 只读取当前模式和平台必需的 reference。
- 快速模式不读取设计文档模板、计划模板、writer/reviewer 指令或完整报告模板。
- 不在对话中重复粘贴 Playbook、模板或工具原始长输出，只报告结论和阻塞证据。
- 进度更新只在模式选择、资源就绪、实现完成、验证完成或出现阻塞时发送；不为每个内部步骤生成状态块。
- 用户随时可以从 `quick` 升级到 `strict`；已有实施摘要可作为设计输入，不重复访谈已确认内容。
