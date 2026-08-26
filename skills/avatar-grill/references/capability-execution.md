# 能力与执行

根据契约中的 `task.kind` 只读取对应行的资料。模块文件是领域事实，不是入口；工具命令从插件根目录执行。

| task.kind | 模块路径 | 关键命令或动作 | 完成证据 |
|---|---|---|---|
| `docs` | `modules/avatar-integration-guides/` 及与问题对应的单个模块 | 只读工程、资料或工具源码后直接回答 | 回答标注事实来源；不写工程、不创建契约 |
| `sdk_build` | `modules/avatar-executing/`、`modules/avatar-preflight/`、`modules/avatar-artifact-download/` | `sdk_artifact.py ensure`；Web 用 `web_delivery.py run`；Android/iOS 按真实产物构建 | `.runtime/verification-result.json`，含构建、连接、首帧、目标交互和安全门禁 |
| `sdk_extend` | `modules/avatar-executing/` 加目标能力模块 | 扫描现有工程；读取实际 SDK API；实现目标能力并回归 | `.runtime/verification-result.json`，新能力与原链路均通过 |
| `web_template` | `modules/avatar-web-template/` | `xfyun_template.py list-templates/create/publish/query` | `.runtime/artifacts.json`，实际 sceneId、模板、app 配对和发布状态 |
| `live_streaming` | `modules/avatar-live-streaming/` | `xfyun_live.py list/list-assets/create/query` | `.runtime/artifacts.json`，直播项目、实际资产和发布/可用状态 |
| `webapi` | `modules/avatar-webapi-protocol/`、`modules/avatar-credentials/` | 读取协议/签名资料；构建并运行真实 WebSocket demo 或现有后端测试 | 连接、请求、响应、终态事件和安全扫描证据 |
| `credentials` | `modules/avatar-credentials/` | `xfyun_common.py login/projects`；`xfyun_query_services.py`；`write_env_safe.py` | `.env` 键存在且未回显；appType、授权和凭据完整性查询通过 |
| `resource_management` | `modules/avatar-credentials/`、`modules/avatar-artifact-download/` | `xfyun_interface.py list/query/create/auth-avatar/list-assets` | `.runtime/artifacts.json`，app/scene 配对、发布状态和实际资产授权 |
| `model_config` | `modules/avatar-model-config/` | `xfyun_model_manage.py list/check/query/create/bind/publish` | `.runtime/artifacts.json`，绑定后的 nlpType 和发布状态复查通过 |
| `knowledge_base` | `modules/avatar-knowledge-base/` | `xfyun_knowledge.py list/create-kb/upload/enable/status` | `.runtime/artifacts.json`，文档就绪、关联、调用链和发布状态 |
| `configuration` | `modules/avatar-config-authoring/` 及目标能力模块 | 读取现值，按契约更新，再重启或重查 | 新配置值与目标运行行为的证据 |
| `permissions` | `modules/avatar-permissions-setup/` | 修改平台声明和运行时请求；只实现契约已确认权限 | 构建通过，授权/拒绝路径可运行且未新增未授权权限 |
| `diagnose` | `modules/avatar-troubleshoot/`、`modules/avatar-network-debug/` | 收集错误码、日志、关闭码、平台查询；按契约仅实施最窄工程修复并复现 | 原故障消失，回归门禁通过；外部阻塞则给出恢复条件 |
| `verify` | `modules/avatar-verification/` | 按 `platform-gates.md` 检查现有工程或平台资源 | `.runtime/verification-result.json` 或 `.runtime/artifacts.json` |

## SDK 平台规则

`sdk_build` / `sdk_extend` 根据契约启用能力再读取对应模块：文本播报 `modules/avatar-text-driver/`，文本问答 `modules/avatar-text-interact/`，音频驱动 `modules/avatar-audio-driver/`，短语音 `modules/avatar-voice-interact/`，全双工 `modules/avatar-full-duplex/`，动作 `modules/avatar-action-control/`，字幕 `modules/avatar-subtitle-setup/`，透明背景 `modules/avatar-transparent-bg/`，工具链 `modules/avatar-toolchain/`。未启用的能力模块不读取、不实现。

### Web

1. 后端持有 apiKey/apiSecret，前端只请求 `/api/config` 与 `/api/avatar-auth`。
2. 读取实际 `index.d.ts` 后实现。
3. 只用 `web_delivery.py run` 编排凭据、SDK、服务、浏览器证据和完成门禁。

### Android

1. 读取 `modules/avatar-executing/references/android-sdk-build-playbook.md` 全文和实际 AAR。
2. 使用预置模板，按 `modules/shared/android-gradle-stability.md` 串行构建。
3. 写完检查 Android API 黑名单零命中；语音未确认时不得加入 `RECORD_AUDIO`。

### iOS

1. 从实际 framework/header 核对 API。
2. 配置 Embed & Sign、系统库、Bundle ID 和 Team。
3. 构建证据和真机首帧/交互证据分开记录。

## 只读、写操作和重试

- `docs` 直接回答，不生成写操作契约。
- docs、verify 只允许 [] 或 [none]；diagnose 只允许空操作、create_project_files 或 update_config，其他平台写操作必须回到 Grill 重新确认契约。
- 任何工程或平台写操作必须同时满足用户确认和 `allowed_mutations` 授权。
- mutation 按本轮资源模式和操作意图声明：已有 SDK/`.env` 不强制下载或写入；知识库和模型复用不强制创建、绑定或发布；scene 仅在 `mode=create` 时要求创建授权，仅在明确发布时要求发布授权。
- 平台工具失败时读取结构化 `next_action`；修复后重复同一任务并重新查询副作用。
- 同一阻塞连续两次没有新证据时停止自动重试，记录外部恢复条件。
