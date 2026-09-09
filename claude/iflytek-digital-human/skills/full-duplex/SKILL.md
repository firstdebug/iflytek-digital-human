---
name: full-duplex
description: 全双工语音交互和打断功能
tags:
  - feature
  - full-duplex
  - interrupt
  - realtime
---

# avatar-full-duplex: 全双工与打断

## 功能说明

**全双工语音交互**: 实时语音识别与理解，无需等待录音结束，边说边识别。

**打断播报**: 在虚拟人播报过程中主动中断，适用于用户打断、紧急消息等场景。

**前置条件**:
- 全双工需开通服务能力
- 打断功能所有版本均支持

---

## 调用时机

需要以下能力时调用本技能:
- 在虚拟人播报过程中主动中断（用户打断、紧急消息）
- 实时边说边识别（自然对话、实时交互）
- 配置追加/打断交互模式

---

## 核心工作流概览

| 能力 | 关键 API | 前置条件 |
|------|----------|----------|
| 打断播报 | `avatar.interrupt()` | 无（所有版本支持） |
| 打断后续播 | `interrupt()` + `writeText()` | 无 |
| 打断模式配置 | `interactive_mode: 1` | 无 |
| 全双工启用 | `asr.full_duplex: true` | 开通全双工服务能力 |
| 实时识别 | 监听 `SDKEvents.asr` | 全双工已启用 |
| VAD 端点检测 | 监听 `SDKEvents.vad`，录音 `vad: true` | 推荐配合全双工 |

---

## 决策分支（场景 → 应读哪个 reference）

- 需要**打断播报**（立即中断、打断后续播、打断模式配置）→ 见 `references/interrupt-implementation.md`（含 Web / Android / iOS 完整实现）
- 需要**全双工语音交互**（启用全双工、实时识别、VAD 端点检测）→ 见 `references/full-duplex-implementation.md`（含 Web / Android / iOS 完整实现）
- 需要**完整应用场景示例**（智能客服、实时对话、紧急消息、交互式教学）→ 见 `references/scenarios.md`
- 遇到**问题排查**（打断不生效、全双工未生效、识别延迟、VAD 误触发）→ 见 `references/troubleshooting.md`

---

## 关键约束 / Red Flags

- **全双工服务能力**: 全双工必须在平台控制台开通服务能力，否则 `full_duplex: true` 不生效。
- **打断状态**: 打断仅在播报中有效；播报已结束或未在播报状态时调用 `interrupt()` 不生效。需要时监听 `frame_start` / `frame_stop` 判断状态。
- **交互模式二选一**: `interactive_mode = 0`（追加，排队等待）与 `= 1`（打断，立即中断）语义相反，配置前确认场景需求。
- **网络要求**: 全双工对网络要求较高，弱网下实时识别延迟明显。

---

## 短语音 vs 全双工

| 特性 | 短语音交互 | 全双工交互 |
|------|-----------|-----------|
| **识别时机** | 录音结束后 | 实时边说边识别 |
| **延迟** | 2-5 秒 | < 1 秒 |
| **网络要求** | 中等 | 较高 |
| **适用场景** | 问答、指令 | 自然对话、实时交互 |
| **服务要求** | 基础 ASR | 全双工能力 |

**推荐**:
- 问答型场景 → **短语音交互**
- 对话型场景 → **全双工交互**

---

## references/ 索引

| Reference 文件 | 内容 |
|----------------|------|
| `references/interrupt-implementation.md` | 打断播报多平台实现：立即中断、打断后续播、打断模式配置（Web / Android / iOS） |
| `references/full-duplex-implementation.md` | 全双工多平台实现：启用全双工、实时识别、VAD 端点检测（Web / Android / iOS） |
| `references/scenarios.md` | 完整应用场景示例：智能客服、实时对话、紧急消息、交互式教学 |
| `references/troubleshooting.md` | 常见问题排查：打断不生效、全双工未生效、识别延迟、VAD 误触发 |

---

## 配置清单

### 打断功能
- [x] 调用 `interrupt()` 方法
- [x] 可选：配置 `interactive_mode = 1`（自动打断）
- [x] 监听播报状态（可选）

### 全双工功能
- [x] 开通全双工服务能力
- [x] 启用 `full_duplex: true`
- [x] 启用 VAD（推荐）
- [x] 监听 `asr` 事件处理实时结果
- [x] 监听 `vad` 事件处理端点检测

---

## 相关技能

- `voice-interact`: 语音交互（短语音模式）
- `text-interact`: 文本交互（NLP）
- `avatar-permissions-setup`: 麦克风权限配置
