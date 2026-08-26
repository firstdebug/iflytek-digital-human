> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。

# SDK 工程执行资料

## 输入与结果

唯一业务输入是已确认且通过 `scripts/validate_contract.py` 校验的执行契约。主 Agent 根据契约中的 `task.kind`、平台、启用/排除能力、资源、`allowed_mutations` 和验收条件直接实现。

结果必须是实际工程改动和确定性证据，不用过程报告代替构建、运行或平台查询。

## 执行前门禁

1. 插件根目录存在 `tools/xfyun_common.py`。
2. 契约状态允许执行，`confirmation.confirmed=true`。
3. 本轮写操作都包含在 `allowed_mutations` 中。
4. appId、sceneId、发布状态、资源授权和 SDK 来源已由平台工具或实际产物验证。
5. `features.enabled` 与 `features.excluded` 已明确；未确认语音时不得写录音代码或麦克风权限。

## 平台事实隔离

写 SDK 代码前必须完成下列读取，不能用记忆、简化示例或其他平台 API 代替：

| 平台 | 写代码前必须读取 | 权威事实 |
|---|---|---|
| Web | `references/web-sdk-build-playbook.md` 全文和下载 SDK 的实际 `index.d.ts` | 导出方式、`setApiInfo`、`setGlobalParams`、`start`、目标驱动方法 |
| Android | `references/android-sdk-build-playbook.md` 全文、实际 AAR 或其中已实测签名 | 初始化顺序、播放器、监听器、参数、依赖和 API 黑名单 |
| iOS | 下载 SDK 的 framework/header | 类名、方法签名、初始化、系统库和 Embed & Sign |

`avatar-integration-guides` 只用于理解概念，不能作为 SDK API 权威来源。通用隔离规则见 `references/anti-hallucination-checklist.md`，Android 实测事实和黑名单见 `references/avatar-code-writer.md`。

## Web

1. 后端保存 apiKey/apiSecret；前端只获得 appId、sceneId 和服务端签名的 `signedUrl`。
2. WS 基址只能由根目录 `tools/platform_endpoints.py` 提供。
3. 用 `tools/sdk_artifact.py ensure --platform web --project <project>` 下载并校验 SDK。
4. 读取实际 `index.d.ts` 后实现，前端模块按产物事实处理 `module.default`。
5. 使用唯一编排入口：

```bash
python "<repo-root>/tools/web_delivery.py" run --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" --interaction "<text|voice|audio>"
```

退出码 2 是可修复阻塞，3 是等待真实浏览器证据，0 且 `ready_to_deliver=true` 才可完成。不得直接运行 `web_sdk_gate.py`、手写运行证据或单独调用完成上报。

## Android

1. 使用 `references/android-mainactivity-template.java` 和 `templates/android-build-template/` 中的构建模板。
2. 依据 `references/android-sdk-build-playbook.md` 配置 AAR、jniLibs、okhttp、gson、播放器和参数顺序。
3. 依据 `modules/shared/android-gradle-stability.md` 串行构建；冷缓存先在线预热，再离线复验。
4. 写完执行黑名单扫描，必须零命中：

```bash
rg -n "createStreamPlayer|sendText|onNlpResult|onAsrResult|onAvatarReady|writeAudioFrame|startAudioInteract|setApiKey\\(" <project>
```

5. 构建成功不等于真机成功；首帧、音视频和交互必须记录真机或模拟器的真实证据。

## iOS

1. 从实际 framework/header 核对类名与签名后再写代码。
2. 配置 Embed & Sign、系统库、Bundle ID 和 Team。
3. 只有契约启用语音且确认麦克风权限后才加入 `NSMicrophoneUsageDescription`。
4. 分开记录编译、安装、连接、首帧和目标交互证据。

## 完成判定

读取根资料 `references/platform-gates.md`。SDK/本地工程由工具写入 `.runtime/verification-result.json`；平台资源由工具重新查询并写入 `.runtime/artifacts.json`。所有验收项通过且无未解决 Critical 问题后，才把契约更新为 `completed`。
