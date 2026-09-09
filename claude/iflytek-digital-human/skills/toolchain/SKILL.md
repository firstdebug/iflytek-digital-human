---
name: toolchain
description: >-
  由 avatar-preflight Layer 5 调用，按 platform 参数走 web / android / ios
  分支做工具链与运行环境检查，逐项检查后经 summarizeStatus 汇总，输出 all_ok / warnings / critical_issues
  三态之一。
tags:
  - toolchain
  - web
  - android
  - ios
  - environment
priority: medium
---

# toolchain: 平台工具链检查

## 定位

平台工具链与运行环境检查，由 `avatar-preflight` Layer 5 调用。按传入的 `platform`
参数分派到 web / android / ios 三个分支，各分支执行本平台的逐项检查，最终统一汇总
为 `all_ok` / `warnings` / `critical_issues` 三态之一交回父流程。

三平台共享同一套骨架：定位、触发时机、逐项检查→`summarizeStatus` 汇总的通用工作流、
三态输出契约。各平台**不同的载荷**（检查项清单、检测实现、修复模板、状态分类规则）
分别落在 `references/` 下的三个 platform 文件。

---

## 触发条件 / 调用时机

- 由 `avatar-preflight` 的 Layer 5（平台工具链检查）在预检阶段调用。
- 输入：目标 `platform`（web / android / ios）与工程路径。
- 目标：确认本地工具链与运行环境满足虚拟人 SDK 运行要求。
- 输出：`status`（all_ok / warnings / critical_issues）+ 各检查项结果；
  `critical_issues` 时应阻断后续构建 / 编译 / 发布流程。

---

## 通用工作流概览

无论哪个平台，流程一致：

1. 按 `platform` 读取对应 platform reference，取得该平台的检查项清单与检测实现。
2. 依次执行各检查项（数量与内容随平台不同），收集每项的 `status` 与结果。
3. 将全部检查结果交给 `summarizeStatus`，按平台的状态分类规则归入 critical / warnings。
4. 由 `summarizeStatus` 返回三态之一，连同各检查项明细交回 `avatar-preflight`。

主编排函数（`checkWebToolchain` / `checkAndroidToolchain` / `checkIOSToolchain`）的
差异仅在于「调用哪些检查、以什么顺序」，其尾部都统一调用 `summarizeStatus(checks)`。
各平台的检查顺序与主编排代码见对应 platform reference。

---

## 决策分支（platform → 应读哪个 reference）

| platform | 参考文件 | 载荷内容 |
|----------|----------|----------|
| web | `references/web-checks.md` | Node.js / 包管理器 / 构建工具 / HTTPS / ESM / 浏览器 / 静态服务器 的检查项、检测实现、修复模板、状态分类 |
| android | `references/android-checks.md` | Gradle / SDK / JDK / NDK / ABI / 依赖 / 构建配置 / 签名 的检查项、检测实现、修复模板、状态分类，及常见问题排查。构建执行、超时处理和离线验收必须遵循 `../shared/android-gradle-stability.md` |
| ios | `references/ios-checks.md` | Xcode / Deployment Target / CocoaPods / Framework / 系统库 / Build Settings / Info.plist / 签名 的检查项、检测实现、修复模板、状态分类，及常见问题排查 |

场景细分（在选定 platform reference 内进一步定位）：

- 需要单个检查项的检测方法 / 判断代码 / 修复建议 → 对应 platform reference 中该检查项小节。
- 需要完整编排流程（主 `check*Toolchain` 函数）与该平台状态分类 → 对应 platform reference 的「完整检查流程 / 状态分类」小节。
- 需要输出格式示例（成功 / 警告 / 关键问题） → 对应 platform reference 的「输出格式」小节。
- 遇到运行 / 编译报错（Android：Gradle 同步、AAR 未识别、UnsatisfiedLinkError；iOS：dyld 加载失败、签名失败、Bitcode 错误、录音崩溃） → 对应 platform reference 的「常见问题修复」小节。

---

## 三态输出格式契约

所有平台的最终输出遵循同一结构，仅 `platform` 与 `checks` 明细不同：

```yaml
status: "all_ok" | "warnings" | "critical_issues"
platform: "web" | "android" | "ios"
# all_ok 时可省略 issues；warnings / critical_issues 时列出问题
issues:
  - "问题描述（含修复指引）"
checks:
  <检查项名>:
    status: "<该项状态>"
    # 视检查项附带 version / current / required / fix 等字段
```

- `all_ok`：无 critical、无 warning。
- `warnings`：无 critical，但存在建议修复项，不阻断流程。
- `critical_issues`：存在硬性阻断项，应中止后续流程。

各平台成功 / 警告 / 关键问题的具体字段示例见对应 platform reference 的「输出格式」小节。

---

## summarizeStatus 通用实现

三平台的 `summarizeStatus` 骨架逐字相同，此处合成为**唯一一份**通用实现：先收集
`critical` 与 `warnings` 两个数组，再按「有 critical → critical_issues；否则有 warning →
warnings；否则 all_ok」返回三态。中间「哪个检查项的哪个 status 归入 critical / warning」
是**平台特定分类规则**，见各 platform reference 的「状态分类」小节，按平台填入注释处即可。

```javascript
function summarizeStatus(checks) {
  const critical = [];
  const warnings = [];

  // —— 平台特定分类规则 ——
  // 按对应 platform reference 的「状态分类」小节，将各检查项 status
  // push 进 critical 或 warnings。例如：
  //   critical.push('<硬性阻断项描述>');
  //   warnings.push('<建议修复项描述>');

  if (critical.length > 0) {
    return { status: 'critical_issues', issues: critical };
  } else if (warnings.length > 0) {
    return { status: 'warnings', issues: warnings };
  } else {
    return { status: 'all_ok' };
  }
}
```

---

## 关键约束 / Red Flags

通用原则：

- 逐项检查 → `summarizeStatus` 三态汇总；`critical_issues` 阻断后续流程。
- 区分必需与可选检查；提供多种修复方案并给出具体命令 / 代码。
- 只在预检阶段能静态判断的项做判断；运行时项（如浏览器兼容性）仅提供检测片段。

平台硬性约束（HARD-GATE，详见各 platform reference）：

- **Web**：录音场景下 HTTPS 缺失（非 localhost / 非 HTTPS）为 critical；ESM 未配置为 warning（SDK 为 ESM 格式）。
- **Android**：`minSdkVersion 21` 为硬性要求，< 21 判 critical；Gradle / Android SDK / JDK 任一未装判 critical；必需依赖 okhttp（3.11.0+）缺失判 critical；SDK 仅支持 ABI `armeabi-v7a` / `arm64-v8a`；`jniLibs.srcDirs = ['libs']` 为加载 so 库的必需配置。
- **iOS**：macOS 专属；Deployment Target ≥ 11.0（低于判 critical）；Framework 必须 `Embed & Sign`（未嵌入导致 `dyld: Library not loaded`）；`Enable Bitcode = NO`；`VALID_ARCHS = arm64`；录音功能必须配置 `NSMicrophoneUsageDescription`。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/web-checks.md` | Web 平台 7 项检查（Node.js / 包管理器 / 构建工具 / HTTPS / ESM / 浏览器 / 静态服务器）：检查方法、判断逻辑、修复模板、`checkWebToolchain` 编排、状态分类、输出格式 |
| `references/android-checks.md` | Android 平台 8 项检查（Gradle / SDK / JDK / NDK / ABI / 依赖 / 构建配置 / 签名）：bash 检查方法、YAML 要求、JS 判断、修复 / 配置模板、`checkAndroidToolchain` 编排、状态分类、输出格式、常见问题修复 |
| `references/ios-checks.md` | iOS 平台 8 项检查（Xcode / Deployment Target / CocoaPods / Framework / 系统库 / Build Settings / Info.plist / 签名）：检测代码、要求、修复建议、`checkIOSToolchain` 编排、状态分类、输出格式、常见问题修复 |

---

## 验证清单

按 platform 选取对应清单：

**Web**
- [ ] HTTPS：录音场景下确认 https_enabled 或 localhost_ok；否则报 critical。
- [ ] ESM：确认 esm_enabled / esm_supported；否则报 warning 并给出修复方案。
- [ ] Node.js：版本 >= 14（推荐 >= 18）；过低报 warning。
- [ ] 无构建工具时：确认至少一个静态服务器可用。
- [ ] 输出符合三态结构。

**Android**
- [ ] Gradle ≥ 7.0（推荐 7.4+）
- [ ] ANDROID_HOME 已配置，minSdkVersion ≥ 21
- [ ] JDK ≥ 8（推荐 11/17）
- [ ] 必需依赖 okhttp ≥ 3.11.0 已引入
- [ ] ABI 仅含 armeabi-v7a / arm64-v8a
- [ ] jniLibs.srcDirs = ['libs'] 已配置
- [ ] Release 构建已关联签名配置（发布场景）

**iOS**
- [ ] Xcode 已安装且版本 ≥ 12.0
- [ ] iOS Deployment Target ≥ 11.0
- [ ] AvatarSDK.framework（及 XRTCSDK）已 Embed & Sign
- [ ] 系统库已链接（libc++.tbd、SystemConfiguration、AVFoundation）
- [ ] Enable Bitcode = NO，VALID_ARCHS = arm64
- [ ] 使用录音时已配置 NSMicrophoneUsageDescription
- [ ] 真机运行时 Team 与 Bundle ID 已配置、证书有效

通用：
- [ ] 汇总状态经 `summarizeStatus` 返回三态并交回 `avatar-preflight`。

---

## 相关技能

- `avatar-preflight`: 调用本技能的父流程（Layer 5）
