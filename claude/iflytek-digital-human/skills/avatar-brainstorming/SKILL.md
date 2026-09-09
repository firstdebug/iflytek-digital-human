---
name: avatar-brainstorming
description: 虚拟人集成任务的需求澄清阶段（三阶段工作流第一阶段）
tags:
  - brainstorming
  - requirements
  - design-spec
priority: high
---

# avatar-brainstorming: 需求澄清

## 定位

三阶段工作流的 **Phase 1: 需求澄清与设计**，负责从用户需求到设计文档的转换。

先读 `../shared/delivery-modes.md`，接收上游 `workflow_mode: quick | strict`。

- `quick`：不创建 `design-spec.md`，不调用 `spec-reviewer`，在当前上下文维护不超过 12 行的实施摘要后直接调用 `avatar-executing`。
- `strict`：继续本流程生成并评审设计文档。

模式不明确时返回上游询问用户，不能默认 quick。

## 触发条件 / 调用时机

- 用户发起虚拟人集成任务（首次接入、功能扩展、配置调整）
- 需求进入需要澄清、访谈、生成设计文档的阶段
- 作为三阶段工作流的第一阶段被调用，输出 `design-spec.md` 后移交 `avatar-planning`

## 核心工作流概览

```
Phase 1: 扫描工程现状
Phase 2: 环境门禁（HARD-GATE）
Phase 3: 意图分类
Phase 4: 需求访谈与方案探讨
Phase 5: 生成设计文档
Phase 6: 设计文档评审（spec-reviewer）
Phase 7: 用户确认

→ 输出: 设计文档 (design-spec.md)
→ 下一步: avatar-planning
```

**HARD-GATE: 按 workflow_mode 决定 Phase 5/6/7**

Phase 1-4（扫描、门禁、意图分类、需求确认）**两种模式都要执行**。Phase 5-7 按模式分流：

| 模式 | Phase 4 需求确认 | Phase 5 设计文档 | Phase 6 spec-reviewer | Phase 7 用户确认 |
|------|-----------------|-----------------|----------------------|-----------------|
| `quick` | 一次紧凑提问补齐会改变实现路径的信息 | ❌ **不创建 `design-spec.md`** | ❌ **不调用 `spec-reviewer`** | 仅确认实施摘要边界 |
| `strict` | 走完访谈主题（核心功能/视觉效果/协议/形象声音） | ✅ 10 章完整文档 | ✅ 调用评审 | ✅ 展示文档并等待明确确认 |

`quick` 模式下 Phase 4 结束后**直接调用 `avatar-executing`**，携带不超过 12 行的实施摘要。

`strict` 模式禁止以下跳过行为：

- ❌ "用户需求已明确" → 直接写代码
- ❌ "参数都给了" → 跳过访谈
- ❌ "简单需求" → 不生成设计文档
- ❌ "我理解了" → 不走评审

**两种模式都不能跳过的**：平台与功能边界确认、凭据与资源验证、语音等敏感能力的单独确认、真实
Playbook 读取。未确认的能力必须写入实施摘要的 `excluded`，不得因"虚拟人对话"就自行加入麦克风、
语音或动作能力。

**例外**：意图分类后直接路由到其他技能（故障排查/配置调整）时，Phase 4-7 不适用。

| Phase | 名称 | 目的 | 详细参考 |
|-------|------|------|----------|
| 1 | 扫描工程现状 | 平台识别、SDK 状态、工具链扫描 | `references/project-scanning.md` |
| 2 | 环境门禁 | 调用 avatar-preflight（HARD-GATE） | `references/project-scanning.md` |
| 3 | 意图分类 | 明确任务类型，决定后续流程 | `references/intent-classification.md` |
| 4 | 需求访谈 | 交互式访谈，明确技术选型 | `references/interview-templates.md` |
| 5 | 生成设计文档 | 结构化访谈结果 | `references/design-doc-template.md` |
| 6 | 设计文档评审 | 调用 spec-reviewer 子代理 | `references/review-and-output.md` |
| 7 | 用户确认 | 展示文档并确认下一步 | `references/review-and-output.md` |

## 决策分支（场景 → 应读哪个 reference）

- **需要扫描平台 / SDK 集成状态 / 工具链** → 读 `references/project-scanning.md`（含扫描规则与 Phase 2 门禁调用代码）
- **需要判断任务类型（首次接入 / 功能扩展 / 故障排查 / 配置调整 / 文档查询）** → 读 `references/intent-classification.md`
- **需要展开访谈问题（AskUserQuestion 模板）** → 读 `references/interview-templates.md`
  - 首次接入访谈 → 见 4.1
  - 功能扩展访谈 → 见 4.2
  - 配置调整访谈 → 见 4.3
- **需要生成设计文档** → 读 `references/design-doc-template.md`（完整 10 章模板）
- **需要评审与用户确认、组织成功/异常输出** → 读 `references/review-and-output.md`

意图路由的下游技能：
- 故障排查 → 路由到 `avatar-troubleshoot`
- 配置调整 → 路由到 `avatar-config-authoring`
- 首次接入 / 功能扩展 → 继续 Phase 4 访谈

## 关键约束 / HARD-GATE / Red Flags

### HARD-GATE: 环境门禁（Phase 2）
- **首次接入必须通过全部检查**（sdk_status = not_integrated 强制触发）
- 功能扩展可跳过部分检查（如工具链已验证）
- 用户可选择跳过，但**必须明确风险提示**
- 门禁全部 PASS 后，保存环境配置到 `dev-env.yaml`

### Red Flags（需警告用户）
- 新功能需要更改现有配置（如透明背景需将协议从 webrtc 改为 xrtc）→ 警告可能影响现有功能，建议独立分支测试，并确认是否继续
- 调整分辨率/码率等参数会影响带宽和解码性能 → 生成影响分析并确认用户理解同意
- 透明背景仅 XRTC 协议支持 → 协议选择必须与透明背景需求一致

### 其他关键约束
- **意图分类准确性**: 优先识别故障排查和配置调整，避免走完整流程；模糊需求时引导用户明确，不要猜测
- **访谈效率**: 利用工程扫描结果预填答案；利用 `dev-env.yaml` 缓存避免重复询问；分批访谈，避免一次性提问过多
- **设计文档质量**: 必须包含完整的参数配置示例；必须覆盖错误处理；必须明确权限和环境要求
- **用户体验**: 进度可视化（Phase 1/7）；关键决策点提供说明和参考链接；异常时给出明确的下一步建议
- **安全**: 凭据配置不包含明文 apiSecret；日志脱敏

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/project-scanning.md` | Phase 1 平台识别/SDK 状态/工具链扫描规则与输出，Phase 2 门禁调用代码 |
| `references/intent-classification.md` | Phase 3 意图识别规则表与分类示例（首次接入/功能扩展/故障排查） |
| `references/interview-templates.md` | Phase 4 访谈主题与 AskUserQuestion 模板（首次接入/功能扩展/配置调整） |
| `references/design-doc-template.md` | Phase 5 设计文档完整 10 章模板（概述/需求/技术选型/架构/实现/测试/部署/风险/资源/变更） |
| `references/review-and-output.md` | Phase 6 评审维度与输出，Phase 7 用户确认，成功/异常输出结构 |

## 验证清单 / 交接协议

进入下一阶段前确认：
- [ ] 平台已识别（或已通过 AskUserQuestion 明确）
- [ ] 环境门禁已通过或用户已知风险选择跳过
- [ ] 意图已分类，非集成任务已正确路由
- [ ] **Phase 4 访谈已完成（有 AskUserQuestion 调用记录，至少覆盖核心功能主题）**
- [ ] **Phase 5 设计文档已生成（文件存在，包含10章完整结构）**
- [ ] **Phase 6 spec-reviewer 已调用（有评审输出，status: pass）**
- [ ] **Phase 7 用户已确认（有明确回复，非推测）**
- [ ] 访谈完成，技术选型和资源配置已确认
- [ ] 设计文档已生成并通过 spec-reviewer 评审（status: pass）
- [ ] 用户已确认设计文档

**成功交接输出**（详见 `references/review-and-output.md`）:
- `status: "completed"`
- `design_spec_path: "./avatar-integration-spec.md"`
- `next_step: "avatar-planning"`

**HARD-GATE: 禁止跳过后续阶段**:
- 设计文档完成后，**必须立即**调用 `avatar-planning` 生成实施计划
- 计划完成后，**必须立即**调用 `avatar-executing` 执行实现
- **严禁**看完设计文档后直接手写代码（会遗漏关键检查点和参数）
- **Web SDK 自建工程特别注意**: `avatar-executing` 会强制读取 `web-sdk-build-playbook.md`，
  包含 bitrate/1024 陷阱、avatar.stream 字段锁定表、凭据自动写入等**一次运行成功**的关键流程

## 相关技能

- `avatar-preflight`: Phase 2 调用
- `spec-reviewer`: Phase 6 调用
- `avatar-planning`: 下游技能
- `avatar-troubleshoot`: 故障排查路由目标
- `avatar-config-authoring`: 配置调整路由目标
