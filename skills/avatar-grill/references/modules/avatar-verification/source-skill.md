> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。

# 交付前验证资料

## 范围

只验证契约中启用的能力和固定安全门禁。未启用语音时，不检查也不新增麦克风、录音或 ASR。验证结果必须来自命令退出码、构建产物、运行事件、浏览器/设备证据或平台重新查询。

## 七层检查

| 层 | 检查内容 | 完成证据 |
|---|---|---|
| 1 文件 | 必需文件和入口完整 | 文件清单、哈希或静态检查结果 |
| 2 凭据 | `.env` 键存在、未泄露，app/scene 配对并发布 | 安全检查和平台查询 |
| 3 SDK | 产物存在、哈希和入口可读 | `sdk_artifact.py` 结果 |
| 4 依赖 | 包管理依赖完整 | 安装命令退出码和依赖树 |
| 5 配置 | bitrate、协议、事件、资源和权限符合契约 | 静态门禁结果 |
| 6 构建 | 编译和测试通过 | 构建命令退出码与产物 |
| 7 运行 | 连接、推流、首帧和目标交互通过 | 新鲜运行证据 |

配置陷阱见 `references/config-checks.md`，通用验证实现见 `references/verify-workflow.md`。这些资料只提供检查事实，最终完成标准以根资料 `references/platform-gates.md` 为准。

## Web SDK

Web SDK 只通过根目录的确定性状态机验证：

```bash
python "<repo-root>/tools/web_delivery.py" run --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" --interaction "<text|voice|audio>"
```

- 退出码 2：静态阻塞，读取 JSON `next_action` 修复后重复同一命令。
- 退出码 3：等待新鲜的 connected、stream_start、首帧或目标交互证据。
- 退出码 0：工具写入 `.runtime/verification-result.json` 且返回 `ready_to_deliver=true`。

不得直接运行 `web_sdk_gate.py`，不得手写 `.runtime/web-runtime-evidence.json`，不得单独调用遥测完成接口。

## Android 与 iOS

- Android 读取 `modules/shared/android-gradle-stability.md`，串行在线预热并离线复验；命令超时先检查原进程。
- iOS 分别记录构建、安装和真机运行；构建通过不能替代首帧、声音和交互。
- API 黑名单必须零命中，密钥扫描必须通过。

## 平台资源

模板、直播、模型、知识库和接口场景完成写操作后，必须用对应工具重新查询。只有实际 ID、app 配对、发布状态、绑定关系和授权均符合契约，才写入 `.runtime/artifacts.json`。

## 失败与完成

可修复问题保留在同一任务中，修复后重验。存在未解决 Critical 问题时不得交付；明确外部阻塞写明恢复条件。只有所有验收项和平台门禁均通过，才更新契约为 `completed`。
