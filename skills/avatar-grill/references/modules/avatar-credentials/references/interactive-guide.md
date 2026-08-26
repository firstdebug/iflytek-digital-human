# 凭据恢复与安全写入

本资料只处理已确认契约中的凭据恢复，不在执行阶段重新访谈需求，也不要求用户把 apiKey、apiSecret、Cookie 或令牌输入对话。

## 契约门禁

- app、scene 和项目路径来自已确认的 `.avatar/avatar-run-contract.json`。
- 写入 `.env` 时，`resources.credentials.write_env=true` 且 `allowed_mutations` 必须包含 `write_env`。
- 缺少写入授权时停止执行，回到 Grill 修改并重新确认契约。
- `WS_URL` 只能由插件根目录 `tools/platform_endpoints.py` 提供，不接受用户输入或文档中的复制值。

## 安全流程

1. 用 `tools/xfyun_common.py login` 检查本机登录状态；只有浏览器登录动作可由用户完成。
2. 用 `tools/xfyun_query_services.py` 查询 app、scene、发布状态和配对关系，输出只保留脱敏字段。
3. 用 `tools/write_env_safe.py` 从平台查询结果直接写入目标工程 `.env`，完整密钥不得经过模型上下文、命令参数、临时响应文件或标准输出。
4. 检查 `.env` 已被 `.gitignore` 覆盖，再用只读校验验证字段存在、app/scene 配对和在线连接。
5. 平台查询或安全写入失败时保持当前契约为 `blocked_missing_credentials`，记录脱敏错误和可重试命令。

```bash
python "<plugin-root>/tools/xfyun_common.py" login
python "<plugin-root>/tools/xfyun_query_services.py"
python "<plugin-root>/tools/write_env_safe.py" <app-id> <scene-id> <project-path>
```

不得降级为在聊天中逐项索要密钥，也不得把平台事实改成“用户确认即通过”。
