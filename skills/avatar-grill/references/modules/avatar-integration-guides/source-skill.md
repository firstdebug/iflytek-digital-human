> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。


# integration-guides: 三端集成指南索引

## 定位

本资料 是三端 SDK 集成的**快速理解资料**，提供每个平台的最小接入示例，帮助快速建立"这个平台大致怎么接"的认知。

> **⚠️ 生产/自建工程不以本指南为准**：真正构建可交付的 SDK 工程时，必须走
> `avatar-executing/references/*-sdk-build-playbook.md`（HARD-GATE）——那里规定了安全架构
> （后端签名、不在前端硬编码 apiSecret）、字段锁定表和关键陷阱（如 bitrate 会被 SDK /1024）。

## 分平台参考

| 平台 | 文件 | 状态 |
|------|------|------|
| Web | `web.md` | 五分钟最小示例，生产以 web-sdk-build-playbook 为准 |
| iOS | `ios.md` | 原生 iOS 集成快速指南 |
| Android | `android.md` | 已遗弃，唯一权威流程见 `avatar-executing/references/android-sdk-build-playbook.md` |

## 使用建议

- 只想快速了解某平台接入形态 → 读对应平台文件
- 要真正落地可交付工程 → 转 `avatar-executing`，按该平台的 build-playbook 执行

