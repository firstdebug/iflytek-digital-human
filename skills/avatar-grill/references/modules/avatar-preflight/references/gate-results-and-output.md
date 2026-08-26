# 门禁结果与输出

本轮门禁结果只描述当前执行契约对应的工程和平台事实，不写入跨任务权威缓存。

## 通过

```json
{
  "status": "all_pass",
  "contract_id": "avatar-run-...",
  "platform": "web",
  "checks": {
    "credentials": "pass",
    "resources": "pass",
    "sdk": "pass",
    "network": "pass",
    "toolchain": "pass",
    "minimum_runtime": "pass"
  },
  "sources": ["project-scan", "platform-query", "sdk-inspection"],
  "verified_at": "<current-run-timestamp>"
}
```

只有实际执行的检查才能写 `pass`。appId、sceneId、SDK 路径等事实回填到执行契约时必须保留 `source` 和 `verified=true`，密钥值不得写入结果。

## 阻塞

```json
{
  "status": "blocked",
  "contract_id": "avatar-run-...",
  "failed_checks": ["sdk"],
  "evidence": ["expected SDK entry was not found"],
  "recovery_conditions": ["download and verify the selected platform SDK"],
  "retry_commands": ["python tools/sdk_artifact.py ensure ..."]
}
```

检查失败时不能选择跳过或手动绕过来继续交付。保持同一契约为 `blocked`，满足恢复条件后重新执行对应检查；需求或写操作授权变化时回到 Grill 并重新确认契约。
