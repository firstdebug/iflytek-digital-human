# SDK 产物与契约衔接

本资料只描述已确认执行契约中的 SDK 检查和下载，不是独立入口，也不重新询问平台、凭据或功能范围。

## 输入门禁

先读取 `.avatar/avatar-run-contract.json`：

- `resources.sdk.mode=existing`：只检查契约指定或工程扫描发现的实际 SDK 产物，不下载。
- `resources.sdk.mode=download`：`allowed_mutations` 必须包含 `download_sdk`，否则停止并回到 Grill 重新确认契约。
- `resources.sdk.mode=not_required`：不执行 SDK 检查或下载。
- 平台和项目路径只取自契约；缺失或冲突时把当前契约设为 `blocked`。

下载或复用 SDK 不需要重新收集凭据。凭据检查由契约和平台查询负责，密钥不得进入本资料的输入、输出或日志。

## 执行

1. 按契约平台扫描项目中的关键 SDK 文件。
2. 已存在且校验通过时返回 `already_exists`。
3. 契约允许下载时，运行插件根目录的 `tools/sdk_artifact.py ensure`。
4. 校验压缩包、解压路径、SDK 入口、类型文件和哈希。
5. 将相对路径、版本、哈希和本轮校验时间写入 `.runtime/sdk-artifact.json`；它只是当前工程证据，不是跨任务权威缓存。
6. 失败时保持同一契约为 `blocked_missing_sdk`，记录失败证据、恢复条件和可重试命令。

```json
{
  "status": "success",
  "platform": "web",
  "artifact": {
    "entry": "sdk/avatar-sdk-web/esm/index.js",
    "types": "sdk/avatar-sdk-web/esm/index.d.ts",
    "sha256": "<computed-sha256>"
  },
  "source": "sdk-inspection",
  "verified": true
}
```

不得把 HTTP 200、目录非空、文件名或预计下载结果当成通过证据。需求、平台或写操作授权变化时回到 Grill 修改并重新确认契约。
