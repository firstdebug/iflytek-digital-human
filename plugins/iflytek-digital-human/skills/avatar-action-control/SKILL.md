---
name: avatar-action-control
description: 虚拟人动作控制（独立动作和自动动作 AIR）
---

# avatar-action-control: 动作控制

## 功能说明

控制虚拟人执行特定动作（如挥手、点头、鞠躬等）。分为两种模式：

1. **独立动作**: 手动触发特定动作，与播报解耦
2. **自动动作 AIR**: 播报时自动匹配合适的手势和表情

**前置条件**: 形象必须支持动作控制（标准虚拟人支持，超拟人部分支持）

---

## 调用时机

- 需要虚拟人在播报之外执行特定手势/表情时
- 需要播报内容自动伴随手势时（启用 AIR）
- 场景化交互：导览讲解、客服安抚、直播互动等

---

## 核心工作流概览

1. 检查形象是否支持动作控制（`avatar_ready` 事件的 `data.actions`）
2. 选择模式：手动精确控制走独立动作，日常自然表达走 AIR
3. 独立动作：构造 `{ cmd: 'action', params: { action_id } }` 通过 `writeCmds` 发送
4. AIR：`setGlobalParams({ air: { air: true } })` 后正常播报即可自动匹配
5. 可选：监听 `action_start` / `action_stop` 事件

---

## 决策分支（场景 → 应读哪个 reference）

| 你要做的事 | 参考文件 |
|-----------|---------|
| 手动触发单个动作 / 动作序列 / 动作与播报结合（Web/Android/iOS） | `references/independent-actions.md` |
| 启用 AIR 自动动作、了解 AIR 匹配规则（Web/Android/iOS） | `references/air-auto-actions.md` |
| 查询形象支持的动作列表、监听动作事件（Web/Android/iOS） | `references/query-and-events.md` |
| 完整场景示例（导览/客服/直播）与常见问题排障 | `references/scenarios-and-troubleshooting.md` |

具体各平台代码模板一律在对应 reference 文件中，主文件不再重复。

---

## 独立动作 vs 自动动作 AIR

| 特性 | 独立动作 | 自动动作 AIR |
|------|---------|-------------|
| **触发方式** | 手动调用 `writeCmds` | 播报时自动匹配 |
| **控制精度** | 精确控制每个动作 | 智能匹配 |
| **开发成本** | 需编写动作逻辑 | 无需额外代码 |
| **适用场景** | 特定交互、剧本化表演 | 日常对话、讲解导览 |
| **动作丰富度** | 取决于手动编排 | 取决于 AIR 匹配库 |

**推荐**:
- 常规场景使用 **AIR 自动动作**（省力、自然）
- 特殊场景使用 **独立动作**（如仪式性动作、特殊编排）

---

## 关键约束 / Red Flags

- **形象能力**: 形象不支持动作控制时所有动作无效。务必先检查 `avatar_ready` 的 `data.actions`，为空则当前形象不支持。
- **action_id 有效性**: `action_id` 拼写错误或不存在会导致动作不生效。
- **AIR 开关**: AIR 未启用（`air: true`）或形象不支持时不会自动匹配。
- **动作频繁**: AIR 模式下每句话都可能触发动作，必要时调整话术或关闭 AIR 改用手动触发。
- **同步问题**: 独立动作与播报时机不匹配时，使用 AIR 或监听 `frame_start` 后触发。

---

## 配置清单

### 独立动作
- [x] 检查形象是否支持动作
- [x] 获取可用动作列表
- [x] 正确构造动作指令
- [x] 监听动作事件（可选）

### 自动动作 AIR
- [x] 启用 AIR (`air: true`)
- [x] 确认形象支持 AIR
- [x] 优化话术以触发合适动作

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/independent-actions.md` | 独立动作控制：触发单个动作 / 动作序列 / 动作与播报结合（Web/Android/iOS 完整代码） |
| `references/air-auto-actions.md` | 自动动作 AIR：启用 AIR（Web/Android/iOS）、AIR 动作匹配规则与示例 |
| `references/query-and-events.md` | 查询可用动作列表、动作事件监听（Web/Android/iOS） |
| `references/scenarios-and-troubleshooting.md` | 应用场景（导览/客服/直播）完整示例、常见问题排障 |

---

## 相关技能

- `avatar-text-driver`: 文本驱动（可结合动作）
- `avatar-text-interact`: 文本交互（AIR 自动匹配）
- `avatar-brainstorming`: 会询问是否需要动作控制
