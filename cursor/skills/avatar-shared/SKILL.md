---
name: avatar-shared
description: >-
  跨 skill 复用的共享材料容器。收纳与具体平台/业务无关的通用工作方法（测试驱动开发、并行分发子 agent）和共享适配指南（Android
  分区存储）。由其他 skill 按需引用，不单独作为任务入口。
---

# avatar-shared: 共享材料容器

## 定位

本 skill 收纳被多个其他 skill 复用的通用材料，避免重复。它不是任务入口——由 `avatar-executing`
等 skill 在需要时引用，而不是用户直接触发。

## 内容索引

| 材料 | 路径 | 用途 |
|------|------|------|
| 测试驱动开发 | `avatar-test-driven-development/SKILL.md` | 通用 TDD 工作方法（先写测试再实现） |
| 并行分发子 agent | `avatar-dispatching-parallel-agents/SKILL.md` | 把多个独立任务并行派发给子 agent 缩短耗时 |
| Android 分区存储适配 | `android-scoped-storage.md` | Android 11+ (API 30) 分区存储下的日志路径配置 |
| Android Gradle 稳定构建 | `android-gradle-stability.md` | Wrapper 镜像、Maven 顺序、内存/并发、缓存锁与超时处理 |
| 快速/严格交付模式 | `delivery-modes.md` | `workflow_mode: quick\|strict` 的选择、门禁与 token 纪律 |

## 使用建议

- 需要并行处理多个独立任务 → 参考 `avatar-dispatching-parallel-agents`
- 涉及测试策略 → 参考 `avatar-test-driven-development`
- Android 工程遇到 `/sdcard/` 写入受限 → 参考 `android-scoped-storage.md`
- Android 构建慢、卡住、缓存锁或 daemon 异常 → 参考 `android-gradle-stability.md`（构建、预检、排障、验收共用）
- 首次 SDK 自建或多能力扩展要决定过程文档和评审成本 → 参考 `delivery-modes.md`
