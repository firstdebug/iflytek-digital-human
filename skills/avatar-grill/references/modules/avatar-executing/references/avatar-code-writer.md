# SDK API 隔离清单

本文件供主 Agent 写代码前和写完后使用，不定义入口、调度或交接流程。

## 写代码前

- Web：完整读取 `web-sdk-build-playbook.md` 和下载 SDK 的实际 `index.d.ts`。
- Android：完整读取 `android-sdk-build-playbook.md`、实际 AAR 签名和 Android 模板。
- iOS：读取实际 framework/header。
- API 的来源必须是当前插件根目录的工具、真实 SDK 产物或 Playbook；不得根据通用知识补全。

## Android 已验证事实

- NLP 使用 `writeText(text, TextParams)`，并由 `TextParams.setNlp(true)` 启用问答。
- NLP 结果来自 `onResult(type, byte[] data, String extra)` 的 `extra` JSON，按 `request_id` 聚合 status=1 分片，status=2 收尾。
- 播放器使用 `StreamPlayerFactory.createPlayer(ctx, "xrtc")`，并调用 `player.setRenderArea(container)`。
- AAR 不携带所有传递依赖，工程按 Playbook 显式配置 okhttp 和 gson。
- `setGlobalParams` 在 `setStreamPlayer` 前调用；服务地址显式设置为工具提供的 canonical WS URL。
- 接口场景需要实际授权的 avatarId 与 vcn，不得硬编码账号无关的资产 ID。

## Android API 黑名单

真实 SDK 中不存在，写完必须零命中：

```text
createStreamPlayer
sendText
onNlpResult
onAsrResult
onAvatarReady
writeAudioFrame
startAudioInteract
setApiKey(
```

## Web 安全事实

- apiKey/apiSecret 只在服务端；前端只收到服务端生成的 `signedUrl`、appId 和 sceneId。
- WS 基址只能读取 `tools/platform_endpoints.py`，不得从用户文字、搜索或模型记忆获得。
- Web SDK 的导入、初始化和驱动方法必须逐项对照实际 `index.d.ts`。
- `tools/web_delivery.py` 是唯一 Web 交付编排入口；不要手写运行证据或完成状态。

## 写完检查

1. 对 Android 工程运行黑名单 `rg`，命中即停止交付。
2. 对所有平台运行密钥、Cookie、绝对凭据和未脱敏 signed URL 扫描。
3. 检查工具退出码和真实副作用，不把打印的“成功”当成证据。
