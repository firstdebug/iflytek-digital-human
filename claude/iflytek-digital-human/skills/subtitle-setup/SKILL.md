---
name: subtitle-setup
description: 虚拟人字幕配置和显示
tags:
  - feature
  - subtitle
  - caption
---

# avatar-subtitle-setup: 字幕配置

## 功能说明

显示虚拟人播报内容的字幕，适用于无声环境、听力辅助、多语言展示等场景。

**字幕来源**:
- **云端字幕**: 由服务端生成，通过 `subtitle_info` 事件回调返回（简单）
- **客户端字幕**: 自行根据播报文本渲染（灵活）

---

## 调用时机

当用户需要为虚拟人添加字幕/字幕显示、听力辅助、多语言字幕、逐字高亮或视频嵌字幕时使用本技能。

---

## 核心工作流概览

1. 判断字幕来源：标准形象优先云端字幕；透明背景/3D 形象必须客户端渲染。
2. 云端字幕：启用 `subtitle: true` → 监听 `subtitle_info` → 渲染 UI。
3. 客户端字幕：监听 `frame_start`/`frame_stop` 获取文本 → 自行渲染样式。
4. 按需叠加样式定制、逐字高亮、多语言。

| 步骤 | 云端字幕 | 客户端字幕 |
|------|---------|-----------|
| 触发事件 | `subtitle_info` | `frame_start` / `frame_stop` |
| 启用配置 | `subtitle: true` | 无需（监听文本即可） |
| 样式控制 | 有限 | 完全自定义 |
| 兼容性 | 透明背景/3D 不支持 | 全兼容 |

---

## 关键约束 / Red Flags

- **HARD-GATE**: 透明背景和 3D 形象**不支持云端字幕**，必须由客户端自行渲染。
- 云端字幕基于服务端时间戳，存在网络延迟；需精细时机控制时改用客户端字幕。
- 启用云端字幕必须同时设置 `subtitle: true` 并监听 `subtitle_info`，缺一收不到事件。

---

## 决策分支（场景 → reference）

- **启用云端字幕（Web/Android/iOS 完整实现 + 数据结构）** → 详见 `references/cloud-subtitle.md`
- **客户端渲染（基础组件、逐字高亮、多语言双字幕）** → 详见 `references/client-rendering.md`
- **字幕样式定制（基础样式、描边、动画效果）** → 详见 `references/styling.md`
- **应用场景示例（无声环境、听力辅助、语言学习、视频录制）** → 详见 `references/scenarios.md`
- **排障（未收到事件、时机不准、显示不全）** → 详见 `references/troubleshooting.md`

选型建议:
- 标准形象 → **云端字幕**（简单）
- 透明背景/3D → **客户端字幕**（必需）
- 需精细控制 → **客户端字幕**

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/cloud-subtitle.md` | 云端字幕启用（Web/Android/iOS 代码）、`subtitle_info` 数据结构与字段说明 |
| `references/client-rendering.md` | 客户端渲染：基础字幕组件（HTML/CSS/JS）、逐字高亮、中英双语字幕 |
| `references/styling.md` | 字幕样式定制：黑底/白底/描边基础样式、淡入淡出与打字机动画 |
| `references/scenarios.md` | 四类应用场景代码：无声环境、听力辅助、语言学习、视频录制 |
| `references/troubleshooting.md` | 常见问题：未收到字幕事件、时机不准确、显示不全的原因与解决 |

---

## 配置清单 / 验证

### 云端字幕
- [ ] 启用字幕 (`subtitle: true`)
- [ ] 监听 `subtitle_info` 事件
- [ ] 渲染字幕 UI
- [ ] 处理字幕隐藏逻辑

### 客户端字幕
- [ ] 监听 `frame_start` 事件获取文本
- [ ] 设计字幕样式
- [ ] 实现显示/隐藏逻辑
- [ ] 可选：逐字高亮

---

## 相关技能

- `text-driver`: 文本驱动（字幕内容来源）
- `transparent-bg`: 透明背景（需客户端字幕）
- `text-interact`: 文本交互（NLP 回复字幕）
