# 事实隔离与验证清单

本清单由主 Agent 在 API 调用、文件修改和验证时执行。

## API 与数据

- 先读取当前工具源码、Playbook 或真实 SDK 产物，再使用端点、方法签名和 JSON 路径。
- 不根据 REST 命名、域名规律或历史回答拼接 URL。
- 不确定的字段明确标记为待工具验证，不用猜测填充。

## 文件修改

- 修改前读取目标文件并确认当前内容。
- 修改后检查文件存在、语法、依赖和实际副作用。
- 不因缺少设计文档或计划文档而停工；边界只看执行契约。

## 命令与证据

- 以退出码为第一成功信号，再检查产物、进程、端口、运行事件或平台查询。
- Web SDK 只运行 `tools/web_delivery.py`；退出码 2/3 保持任务进行中，退出码 0 且 `ready_to_deliver=true` 才完成。
- 证据文件必须由工具、浏览器、设备或平台查询产生，不能按预期值手写。

## 链接与敏感信息

- WS URL 和控制台入口只能来自 `tools/platform_endpoints.py` 与 `xfyun_common.py projects`。
- 不输出 apiKey、apiSecret、Cookie、Authorization、模型密钥或未脱敏 signed URL。
- 示例使用文档允许的脱敏值，并清楚标为示例。

## 平台专用门禁

- Web 读取实际 `index.d.ts`。
- Android 读取 `android-sdk-build-playbook.md`，并检查 `avatar-code-writer.md` 的黑名单。
- iOS 读取实际 framework/header。
- 语音和麦克风只有在契约明确启用且 `microphone_confirmed=true` 时才实现和验证。
