> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。

# 环境与资源前置检查

`sdk_build` 或环境变化后的 SDK 任务读取本资料，按契约所选平台检查开发条件。本资料不接受用户单独调用，也不产生另一条工作流。

## 检查层

| Layer | 检查 | 资料 |
|---|---|---|
| 0 | 从契约和工程扫描确认 Web/Android/iOS | 本文件 |
| 1 | appId、sceneId、凭据完整性与安全写入能力 | `references/credentials.md` |
| 2 | avatarId、vcn 和资源授权 | `references/resource-authorization.md` |
| 3 | 实际 SDK 产物、入口、哈希和平台依赖 | Web/Android/iOS 对应 implementation 资料 |
| 4 | DNS、TLS、WebSocket 和流媒体网络 | `references/network-validation.md` |
| 5 | Node/JDK/Gradle/Xcode、签名和平台工具链 | Web/Android/iOS 对应 implementation 资料 |
| 6 | 最小连接、首帧和契约目标交互 | 对应平台资料与 `references/network-validation.md` |

按平台只读取必要资料：

- Web：`references/web-implementation.md`
- Android：`references/android-implementation.md`
- iOS：`references/ios-implementation.md`
- 门禁结果：`references/gate-results-and-output.md`

## 执行规则

- 本轮事实只来自执行契约、当前工程扫描、平台查询和实际 SDK 产物。
- 不使用任何跨任务环境缓存作为权威事实；需要复用时也必须重新核对当前工程和平台状态。
- 凭据与资源优先通过插件根目录的 `xfyun_query_services.py`、`xfyun_model_manage.py` 等工具查询，输出保持脱敏。
- apiSecret 不进入对话、契约或日志；安全写入是否允许由 `allowed_mutations` 决定。
- 检查项不得跳过。无法完成或检查失败时，把契约状态设为 `blocked`，记录失败证据、恢复条件和可重试命令，不另开前置检查流程。
- 语音未在契约启用时，不检查或新增麦克风权限。

## 结果

结果格式见 `references/gate-results-and-output.md`。所有检查通过才能继续执行；部分失败保持同一契约，不把建议或预计结果当作通过证据。
