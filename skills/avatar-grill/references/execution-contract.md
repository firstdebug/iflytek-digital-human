# 执行契约

## 1. 作用

`.avatar/avatar-run-contract.json` 是需求确认与执行之间的唯一交接对象。它不是遥测数据，不上传，也不保存密钥。

关键参数只能来自：

- `user`：用户明确决定
- `project-scan`：当前工程读取
- `platform-query`：讯飞平台工具查询
- `sdk-inspection`：实际 SDK 产物检查
- `avatar-platform-constant`：仓库内固定平台常量
- `derived-rule`：可验证的确定性推导

模型常识、历史对话猜测和手工拼接不能作为来源。

## 2. 示例

```json
{
  "schema_version": "1.0",
  "contract_id": "avatar-run-20260826-001",
  "status": "draft",
  "task": {
    "kind": "sdk_build",
    "goal": "创建 Web 文本问答虚拟人",
    "project_path": "D:/tests/avatar-web"
  },
  "platform": {
    "value": "web",
    "source": "user",
    "verified": true
  },
  "features": {
    "enabled": ["text_interact", "subtitle"],
    "excluded": ["voice_interact", "full_duplex", "audio_driver"]
  },
  "resources": {
    "ws_url": {
      "value": "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact",
      "source": "avatar-platform-constant",
      "verified": true
    },
    "app_id": {
      "value": "<verified-app-id>",
      "mode": "existing",
      "source": "platform-query",
      "app_type": 1,
      "verified": true
    },
    "scene_id": {
      "value": "<verified-scene-id>",
      "mode": "existing",
      "source": "platform-query",
      "paired_app_id": "<verified-app-id>",
      "published": true,
      "verified": true
    }
  },
  "decisions": {
    "interaction": "text",
    "protocol": "xrtc",
    "background": "default"
  },
  "allowed_mutations": ["create_project_files", "write_env", "download_sdk"],
  "acceptance": [
    "build_passed",
    "connected",
    "first_frame",
    "text_interaction_passed",
    "secret_scan_passed"
  ],
  "confirmation": {
    "confirmed": false,
    "confirmed_at": null
  },
  "evidence": []
}
```

资源支持三种模式：

- `existing`：值必须已经由平台查询验证。
- `create`：执行阶段创建；确认前不能填写结果 ID。
- `not_required`：该任务不需要此资源，例如只做文档查询。

创建场景的契约可以把 `scene_id` 设为 `{ "mode": "create", "target_app_id": "<verified-app-id>" }`，并在 `allowed_mutations` 中声明 `create_interface_scene`；只有本轮确实要发布时才增加 `publish_scene`。执行后必须回填平台返回的 ID、来源、验证与发布状态，再进入完成状态。这里只是格式说明；实际契约不能保留尖括号占位符。

其他按本轮操作声明的资源字段：

- 已有 SDK：`resources.sdk.mode="existing"`；本轮下载：`mode="download"`，必须授权 `download_sdk`。
- 已有 `.env` 且不改凭据时不声明写入；`resources.credentials.write_env=true` 时必须授权 `write_env`。
- 知识库使用 `resources.knowledge_base.mode="existing|create"`；新建、上传、关联、发布分别用 `create_knowledge_base`、`upload_knowledge`、`enable_knowledge`、`publish_scene`。
- 模型复用使用 `resources.model.mode="existing"`；`bind=true`、`publish=true` 分别要求 `bind_model`、`publish_scene`。不得因 task.kind 自动推断这些写操作。

占位符只能用于文档示例。实际契约不得保留 `<...>`。

### allowed_mutations

`allowed_mutations` 必填，只允许以下值：

| 值 | 授权范围 |
|---|---|
| `none` | 不授权写操作；只读任务也可以使用空数组 |
| `create_project_files` | 创建或修改目标工程文件 |
| `write_env` | 安全写入目标工程环境变量文件 |
| `download_sdk` | 下载并校验 SDK 产物 |
| `create_interface_scene` | 创建接口场景 |
| `publish_scene` | 发布场景 |
| `create_template` | 创建 Web 模板项目 |
| `create_live` | 创建直播项目 |
| `bind_model` | 创建或绑定模型 |
| `create_knowledge_base` | 创建知识库 |
| `upload_knowledge` | 上传知识文档 |
| `enable_knowledge` | 关联或启用知识库 |
| `update_config` | 修改工程或平台配置 |

docs、verify 只允许 [] 或 [none]；diagnose 只允许空操作、create_project_files 或 update_config，其他平台写操作必须回到 Grill 重新确认契约。其他任务按实际资源模式和本轮操作声明对应 mutation；`none` 不能与写操作组合。授权是上限，不代表工具已经执行。

## 3. 状态

- `draft`：事实采集或 Grill 尚未结束，只读操作可继续。
- `confirmed`：用户已确认，允许执行 `allowed_mutations`。
- `executing`：正在修改工程或平台。
- `verifying`：实现结束，正在跑确定性门禁。
- `completed`：验收证据齐全。
- `blocked`：存在明确外部阻塞，记录恢复条件。
- `failed`：明确不可恢复或用户终止。

状态变化不替代遥测状态机。契约是业务执行边界，遥测只记录匿名使用事实。

## 4. 修改规则

- 平台事实重新查询后可以更新，但必须保留新来源和验证状态。
- 用户改变启用能力、平台、目标路径或写操作权限时，回到 `draft` 并重新确认。
- 实现细节调整但不改变需求边界时，不重复询问。
- `completed` 必须包含门禁证据，不能由模型直接写结论。

## 5. 禁止字段

契约任意层级禁止出现：

- `apiKey`、`api_key`
- `apiSecret`、`api_secret`
- `authorization`
- `cookie`
- `access_token`、`refresh_token`
- `password`、`private_key`

只允许记录“密钥已安全取得/已写入受保护位置”的布尔事实，不记录值。
