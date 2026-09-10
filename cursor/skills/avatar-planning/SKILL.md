---
name: avatar-planning
description: 虚拟人集成任务的计划生成阶段（三阶段工作流第二阶段）
---

# avatar-planning: 计划生成

## 准入凭证自检（HARD-GATE）

开始计划前必须执行 `python tools/telemetry.py consent --validate-gate`；返回不是
`valid (accepted)` 或 `valid (declined)` 时拒绝继续并回到 `avatar-consent-gate`。

## 定位

三阶段工作流的 **Phase 2: 计划生成**，负责将设计文档转化为可执行的实现步骤。

## 模式门禁

先读 `../avatar-shared/delivery-modes.md`，接收上游 `workflow_mode: quick | strict`。

- `workflow_mode=quick`：**直接跳过本阶段**，不要读取计划模板，不创建计划文档，不调用 plan-writer/plan-reviewer；把实施摘要直接交给 `avatar-executing`。
- `workflow_mode=strict`：继续本流程。

模式不明确时返回上游询问用户，不能默认 quick。

## 触发条件 / 调用时机

- 上游 `avatar-brainstorming` 已产出设计文档 (`design-spec.md`)
- 用户确认进入计划阶段，需要将设计转为可执行步骤

## 输入

- 设计文档路径 (`design-spec.md`)
- 平台类型 (`web` | `android` | `ios`)
- 实施类型 (`first_integration` | `feature_extension` | `config_adjustment`)

## 输出

- 实现计划文档 (`implementation-plan.md`)
- 下一步：`avatar-executing`

---

## 工作流程概览

```
Step 1: 读取设计文档
Step 2: 调用 plan-writer 生成计划
Step 3: 调用 plan-reviewer 评审计划
Step 4: 用户确认

→ 输出: 实现计划文档
→ 下一步: avatar-executing
```

| Step | 动作 | 详情参考 |
|------|------|----------|
| 1 | 解析设计文档、识别实施范围 | references/design-parsing.md |
| 2 | plan-writer 生成计划（按依赖顺序、含验证与回滚） | references/plan-document-template.md |
| 3 | plan-reviewer 评审（最多 2 轮，只找阻塞问题） | references/review-and-output.md |
| 4 | 展示摘要、用户确认 | references/review-and-output.md |

---

## 决策分支（场景 → 应读哪个 reference）

- 需要从设计文档提取信息、判断实施范围（首次接入 / 功能扩展 / 配置调整）
  → 详见 references/design-parsing.md
- 需要生成实现计划文档，或查看 8 步完整计划模板与各平台代码（Web/Android/iOS）
  → 详见 references/plan-document-template.md
- 需要评审计划、展示摘要给用户确认、组织成功/异常输出
  → 详见 references/review-and-output.md

实施范围快速判断:
- **首次接入** → `scope: full`，6-10 步
- **功能扩展** → `scope: incremental`，3-5 步
- **配置调整** → `scope: minimal`，1-2 步

---

## plan-writer 生成策略（Step 2 概要）

**输入**: 设计文档路径 + 实施范围

```
1. 按依赖顺序组织步骤
2. 每步包含：目标、操作、验证、回滚
3. 标注风险点和注意事项
4. 提供参考代码和文档链接
```

计划文档完整结构（8 步、多平台代码、验证清单、风险点、回滚策略）见 references/plan-document-template.md。

---

## 关键约束 / Red Flags

**凭据安全（HARD-GATE）**:
- apiSecret 不要硬编码，从环境变量或配置文件读取
- apiSecret 不要提交到代码仓库
- 生产环境建议服务端签名，客户端不持有 apiSecret

**必须满足的配置约束**:
- avatarId 和 vcn 必须已授权
- 视频宽高必须为 4 的倍数
- Android/iOS 必须实现运行时权限申请流程（否则录音失败）
- Web 必须处理浏览器自动播放限制

**高风险点（须缓解）**:
1. 凭据配置错误 → 连接失败（缓解: 使用 preflight 验证）
2. 权限未申请 → 录音失败（缓解: 运行时权限检查）
3. 协议配置错误 → 播放失败（缓解: 按设计文档配置）

---

## 验证清单

### 功能验证
- [ ] SDK 初始化成功
- [ ] 虚拟人连接成功
- [ ] 视频播放正常
- [ ] 文本驱动 / 文本交互 / 语音交互工作正常（按需）
- [ ] 透明背景工作正常（如需）

### 异常验证
- [ ] 网络断开后重连
- [ ] 凭据错误时提示明确
- [ ] 权限拒绝时有引导
- [ ] 资源正确释放

### 性能验证
- [ ] 首帧延迟 < 3s
- [ ] 播放流畅无卡顿
- [ ] 内存占用合理

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| references/design-parsing.md | Step 1：设计文档信息提取 schema、实施范围识别（首次接入 / 功能扩展 / 配置调整）示例 |
| references/plan-document-template.md | Step 2.2：完整实现计划文档模板（8 步，Web/Android/iOS 代码、验证清单、风险点、回滚策略） |
| references/review-and-output.md | Step 3-4：plan-reviewer 评审重点与输出、用户确认交互、成功/异常输出结构 |

---

## 注意事项

### 1. 计划粒度
- 每步应该是独立可验证的
- 避免步骤过大或过小
- 首次接入: 6-10 步；功能扩展: 3-5 步；配置调整: 1-2 步

### 2. 代码示例
- 必须提供完整可运行的代码
- 注释关键参数和配置
- 包含错误处理

### 3. 验证方法
- 每步必须有明确的验证清单
- 包含成功标志和失败排查

### 4. 风险管理
- 明确高中低风险，提供缓解措施与回滚策略

### 5. 平台差异
- 同一步骤区分平台实现，标注平台特有的注意事项

---

## 交接协议 / 下一步

**⚠️ 强制流程（HARD-GATE）**：

实现计划已完成，**必须立即调用 avatar-executing skill 执行实现**，严禁主 agent 手动编写代码。

**为什么必须调用 avatar-executing**：
1. avatar-executing 强制读取 playbook（android-sdk-build-playbook.md / web-sdk-build-playbook.md）
2. playbook 包含真实 API 签名、完整模板、构建环境配置，直接手写代码容易用错 API
3. avatar-executing 内置 API 黑名单检测、模板复制、分步验证流程

**如果主 agent 绕过 avatar-executing 直接手写代码**：
- Android: 会用错 API（createStreamPlayer/sendText/onNlpResult 等不存在），编译失败或运行崩溃
- Web: 会遗漏 bitrate 陷阱、前端硬编码 apiSecret、签名错误
- Gradle: 会忘记国内镜像、性能配置，首次编译 20+ 分钟或失败

**正确流程**：
```bash
avatar-planning（生成计划）
    ↓
avatar-executing（读取 playbook → 使用预置模板 → 逐步执行 → 验证）
    ↓
可运行的 APK / Web 应用
```

**错误流程（历史踩坑）**：
```bash
avatar-planning（生成计划）
    ↓
主 agent 直接手写代码（自以为懂 API）
    ↓
编译失败 / 黑屏 / API 不存在 / 构建 20+ 分钟
```

**执行命令**：
```
调用 avatar-executing skill，参数：
- plan_path: implementation-plan.md
- platform: android | web | ios
- task_type: first_integration | feature_extension
```

## 相关技能

- `avatar-brainstorming`: 上游技能（提供设计文档）
- `plan-writer`: Step 2 调用
- `plan-reviewer`: Step 3 调用
- `avatar-executing`: **下游技能（必须调用，不可跳过）**
