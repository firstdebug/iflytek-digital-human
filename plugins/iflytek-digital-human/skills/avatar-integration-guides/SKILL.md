---
name: avatar-integration-guides
description: >-
  三端（Web / Android / iOS）虚拟人 SDK 的"五分钟快速理解"集成指南索引。用于快速了解某一平台的最小接入形态；真正构建可交付工程时以
  avatar-executing 的 build-playbook 为准。
---

# avatar-integration-guides: 三端集成指南索引

## 定位

本 skill 是三端 SDK 集成的**快速理解入口**，提供每个平台的最小接入示例，帮助快速建立"这个平台大致怎么接"的认知。

> **⚠️ 生产/自建工程不以本指南为准**：真正构建可交付的 SDK 工程时，必须走
> `avatar-executing/references/*-sdk-build-playbook.md`（HARD-GATE）——那里规定了安全架构
> （后端签名、不在前端硬编码 apiSecret）、字段锁定表和关键陷阱（如 bitrate 会被 SDK /1024）。

## 分平台参考

| 平台 | 文件 | 状态 |
|------|------|------|
| Web | `web.md` | 五分钟最小示例，生产以 web-sdk-build-playbook 为准 |
| iOS | `ios.md` | 原生 iOS 集成快速指南 |
| Android | `android.md` | 已遗弃，唯一权威流程见 `../avatar-executing/references/android-sdk-build-playbook.md` |

## 使用建议

- 只想快速了解某平台接入形态 → 读对应平台文件
- 要真正落地可交付工程 → 转 `avatar-executing`，按该平台的 build-playbook 执行

## 产品订阅前置

Web、Android、iOS SDK 接入统一使用接口产品 `appType=1`。如果账号没有有效接口产品，
先在插件根目录执行 `python tools/xfyun_subscription.py 1`；当前提交不需要验证码，平台自动审核，
再按平台实际返回查询应用和凭据。Web 模板、PC 助手和数字人直播使用标准产品 `appType=2`，
提交后必须等待运营审核通过，不能直接进入模板创建。
