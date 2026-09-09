---
name: test-driven-development
description: 强制 TDD——写实现代码前先写会失败的测试，再写最小实现让它通过。适用于新增函数/模块/业务逻辑等可单测的代码。虚拟人 SDK 真机交互类（首帧/播放/录音）无法单测的部分走 avatar-verification 的运行时验证，不套本流程。
---

# Test-Driven Development

## When to Use

- 新增一个函数、模块、工具方法、业务逻辑（可被单元测试覆盖的代码）
- 修 bug 时，先用一个复现该 bug 的失败测试锁定它（见 avatar-troubleshoot 无码分支衔接）
- 重构前，先用测试把现有行为固定住

**不适用**：虚拟人 SDK 的真机交互（首帧渲染、播放、录音、WebSocket 连通）——这些无法离线单测，交给 `avatar-verification` 的运行时验证（Layer 7）。

## How It Works（Red → Green → Refactor）

1. **Red**：先写一个测试，描述"这段代码应该做什么"。此时实现还不存在或不完整，**测试必须真的失败**（跑一遍看到红）。
2. **Green**：写**最小**实现，只求让这个测试通过，不多写。跑测试看到绿。
3. **Refactor**：测试保持绿的前提下，清理实现（去重、命名、抽取），每次改完重跑测试确认没弄坏。
4. 循环：下一个行为点，回到 Red。

## 关键纪律

- **先看到红再写实现**。跳过"看到失败"这一步，就无法确认测试真的在测东西——一个永远为绿的测试等于没测。
- **最小实现**。不要为假设的未来需求提前写代码（YAGNI），只让当前测试过。
- **一次一个行为**。别一口气写十个测试再写实现，一个红→绿→重构循环只推进一个点。
- **bug 必先有复现测试**。修 bug 前先写一个能稳定复现它的失败测试，修完它变绿，同时防回归。

## Checklist

- [ ] 实现代码之前，已存在对应测试
- [ ] 该测试在实现前跑过、确实是 FAIL（红）
- [ ] 实现写完后测试转 PASS（绿）
- [ ] 重构后全量测试仍绿
- [ ] 项目无测试框架时，先按语言生态装标准的（JS: vitest/jest；Kotlin: JUnit；Swift: XCTest；Python: pytest）
- [ ] SDK 真机交互部分未强套单测，已交 avatar-verification 运行时验证

## 与其他 skill 的衔接

- `avatar-executing` Step 3：生成业务逻辑代码时按本流程先写测试；SDK 真机部分走 verification。
- `avatar-verification`：承接无法单测的运行时/真机验证，与本 skill 互补（单测管逻辑，verification 管跑起来）。
- `avatar-troubleshoot`：定位到具体逻辑 bug 后，用本 skill 的"复现测试"锁定并防回归。
