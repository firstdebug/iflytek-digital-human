# 模型管理命令与示例

## 目录

- [命令表](#命令表)
- [绑定官方模型](#绑定官方模型)
- [创建并绑定自有模型](#创建并绑定自有模型)
- [更新模型密钥](#更新模型密钥)
- [查询与验证](#查询与验证)
- [错误定位](#错误定位)

所有命令都在 `<plugin-root>` 执行。尖括号内容是运行时输入，不是可直接使用的固定值。

## 命令表

| 任务 | 命令 |
|---|---|
| 列出模型 | `python tools/xfyun_model_manage.py list` |
| 列出场景 | `python tools/xfyun_model_manage.py scenes` |
| 检查场景能力 | `python tools/xfyun_model_manage.py check <sceneId>` |
| 创建自有模型 | `python tools/xfyun_model_manage.py create <name> <model> <introduce> <apiUrl>` |
| 更新模型 | `python tools/xfyun_model_manage.py update <modelId-or-name>` |
| 绑定模型 | `python tools/xfyun_model_manage.py bind <sceneId> <modelName> [systemPrompt]` |
| 发布场景 | `python tools/xfyun_model_manage.py publish <sceneId>` |
| 查询 NLP 配置 | `python tools/xfyun_model_manage.py query <sceneId>` |
| 查询交互配置 | `python tools/xfyun_model_manage.py query-interact <sceneId>` |

## 绑定官方模型

```bash
python tools/xfyun_model_manage.py check <sceneId>
python tools/xfyun_model_manage.py list
python tools/xfyun_model_manage.py bind <sceneId> <officialModelName>
python tools/xfyun_model_manage.py publish <sceneId>
python tools/xfyun_model_manage.py query <sceneId>
```

检查结果没有对话能力时停止绑定，改用具备授权的场景或完成平台授权。

## 创建并绑定自有模型

DeepSeek 等提供 OpenAI 兼容接口的模型按自有模型注册：

```bash
python tools/xfyun_model_manage.py create \
  "<displayName>" "deepseek-chat" "<description>" \
  "https://api.deepseek.com/v1"
```

脚本随后交互读取 API Key，不回显完整值。创建成功后继续：

```bash
python tools/xfyun_model_manage.py bind <sceneId> <displayName>
python tools/xfyun_model_manage.py publish <sceneId>
python tools/xfyun_model_manage.py query <sceneId>
```

预期 `nlpType` 为 `openai`。若平台按 OpenAI 格式拼接 `/chat/completions`，`apiUrl` 应停在 `/v1`，不要重复附加请求路径。

## 更新模型密钥

```bash
python tools/xfyun_model_manage.py update <modelId-or-name>
```

按交互菜单选择 API Key 字段，安全输入新值。更新后查询配置并发起一次真实对话；若场景发布版本未自动刷新，再执行 `publish <sceneId>`。

Windows 自动化输入的稳定做法见 `skills/avatar-credentials/references/windows-secret-input.md`。不要用 PowerShell 对象管道直接喂给 `getpass`。

## 查询与验证

`query` 至少核对：

- 绑定的模型名称和标识
- `nlpType` 是否为 `xinghuo` 或 `openai`
- 自有模型的基础 URL 是否正确
- 场景是否已发布
- 系统提示词是否符合当前任务

配置查询通过不等于服务可用。最后必须发起真实文本交互，确认没有认证、模型不存在或上游限流错误。

如果场景使用知识库，再检查：

```bash
python tools/xfyun_knowledge.py status <sceneId>
```

官方模型通常使用 `docqa,xinghuo`；OpenAI 兼容自有模型使用 `docqa,openai`。

## 错误定位

| 现象 | 原因 | 处理 |
|---|---|---|
| `check` 无对话能力 | 场景未授权 LLM | 更换场景或完成授权 |
| `bind` 成功但对话仍走旧模型 | 未发布 | 执行 `publish` 后重新查询 |
| 自有模型返回认证失败 | API Key 无效或写入错位 | 用 `update` 重录并实际调用 |
| 上游返回 404 | URL 层级或模型标识错误 | 核对 `/v1` 与提供方模型名 |
| 换模型后知识库不命中 | NLP 配置覆盖调用链 | 重新 `enable` 或 `chain` |
| DeepSeek 场景仍走星火 | 链路第二段错误 | 改为 `docqa,openai` 并发布 |
