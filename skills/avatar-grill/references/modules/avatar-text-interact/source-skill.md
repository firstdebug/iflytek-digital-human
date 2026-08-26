> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。


# avatar-text-interact: 文本交互（NLP）

## 功能说明

用户输入文本，经过 NLP 或大模型理解后，虚拟人智能回答。适用于智能客服、知识问答、对话机器人等场景。

**与文本驱动的区别**:
- **文本驱动**: 虚拟人直接朗读输入的文本（TTS）
- **文本交互**: 输入经过 NLP/大模型理解后生成回复，虚拟人播报回复内容

---

## 适用范围

- 需要虚拟人"理解"用户输入并智能生成回复，而非逐字朗读
- 智能客服、知识问答、闲聊、任务型对话等场景

---

## 核心工作流概览

1. 平台侧开通**大模型对话能力**（HARD-GATE，见下）
2. 调用 `writeText(text, { nlp: true })` 发送文本
3. 监听 `nlp` 事件获取理解结果 `answer`
4. 虚拟人自动播报 `answer` 内容
5. 多轮对话时维护 `session_id` / `history` 上下文

| 环节 | 关键点 |
|------|--------|
| 发送 | `nlp: true` 启用 NLP；`stream_nlp: true` 启用流式 |
| 接收 | 监听 `nlp` 事件，读取 `data.answer` |
| 播报 | 虚拟人自动播报，无需手动触发 TTS |
| 上下文 | 通过 `context.session_id` + `history` 维护多轮 |

---

## 决策分支（场景 → 应读哪个 reference）

- 首次接入 / 需要各端最小代码：见 `references/quick-start.md`（Web / Android / iOS 完整快速接入）
- 配置 NLP 参数、流式 vs 非流式、多轮上下文、回复数据结构：见 `references/advanced-config.md`
- 具体业务场景（智能客服 / 知识问答 / 闲聊 / 任务型）：见 `references/use-cases.md`
- 自定义 Webhook、意图动作、情感分析、性能优化：见 `references/advanced-features.md`
- 排障（回复不准 / 延迟高 / 未开通能力 / 上下文丢失）：见 `references/troubleshooting.md`

---

## 关键约束 / HARD-GATE / Red Flags

- **HARD-GATE**: 必须在虚拟人交互平台**开通大模型对话能力**，否则 `nlp` 事件不触发或返回错误。开通路径：控制台 → 接口服务 → 开通"大模型对话能力" → 保存并发布。
- **推荐流式**: 优先使用 `stream_nlp: true`，首句延迟 1-2 秒，非流式为 2-5 秒。
- **Red Flag - 上下文丢失**: 多轮对话未维护 `session_id` 会导致"刚才说了什么"类问题失效。
- **Red Flag - 混淆能力**: 文本交互（`nlp: true`）≠ 文本驱动（直接 TTS 朗读）。不需要理解时不要误开 NLP。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/quick-start.md` | Web / Android / iOS 快速接入完整代码 |
| `references/advanced-config.md` | NLP 参数配置、流式对比、多轮上下文管理、NLP 回复数据结构 |
| `references/use-cases.md` | 智能客服 / 知识问答 / 闲聊 / 任务型对话四类场景代码 |
| `references/advanced-features.md` | 自定义 Webhook、意图动作、情感分析、性能优化 |
| `references/troubleshooting.md` | 常见问题与解决方案 |

---

## 与语音交互的区别

| 特性 | 文本交互 | 语音交互 |
|------|---------|---------|
| 输入方式 | 键盘输入文本 | 麦克风录音 |
| 识别环节 | 无需 ASR | 需要 ASR（语音识别） |
| 理解环节 | NLP/大模型 | NLP/大模型 |
| 回复播报 | TTS 播报 | TTS 播报 |
| 适用场景 | 安静环境不便说话<br>精确输入 | 免手操作<br>自然交互 |
| 网络要求 | 较低 | 较高（实时音频上传） |

---

## 验证清单

### 平台配置
- [ ] 开通大模型对话能力
- [ ] 配置 NLP 服务（平台默认或自定义 Webhook）
- [ ] 配置知识库（如需）

### 代码配置
- [ ] 设置 `nlp: true`
- [ ] 启用 `stream_nlp: true`（推荐）
- [ ] 监听 `nlp` 事件
- [ ] 维护会话上下文（多轮对话）

### 性能优化
- [ ] 使用流式 NLP
- [ ] 缓存常见问答
- [ ] 精简上下文长度

---

