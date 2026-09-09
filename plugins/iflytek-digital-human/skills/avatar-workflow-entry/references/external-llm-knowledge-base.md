# 外部大模型与讯飞知识库

当需求同时包含 DeepSeek、GPT 等外部模型和讯飞知识库、docqa 或 RAG 时使用本文件。

## 原生链路

讯飞平台可将 OpenAI 兼容端点注册为自有模型，再把 docqa 检索结果传给该模型：

1. 使用 `tools/xfyun_model_manage.py create` 注册外部模型，`modelType=2`、`nlpType=openai`。API Key 必须通过交互输入或 `references/windows-secret-input.md` 的临时文件重定向方式提供，不放入命令行。
2. 使用 `tools/xfyun_model_manage.py bind <sceneId> <modelName>` 将模型绑定到场景；自有模型会写入 `nlpType=openai`。
3. 使用 `tools/xfyun_knowledge.py create-label`、`create-kb`、`upload <libId> <文件...> --wait` 创建知识库并上传文档。上传目录时过滤 `.backup`、临时文件和非知识文档。
4. 使用 `tools/xfyun_knowledge.py enable <sceneId> <libId> --chain docqa,openai` 关联场景。
5. 使用 `tools/xfyun_knowledge.py status <sceneId>`、`tools/xfyun_model_manage.py query <sceneId>`、`query-interact <sceneId>` 验证 `docqa`、`openai` 和调用链。

调用链第二段必须与绑定模型的 `nlpType` 一致。自有 OpenAI 兼容模型使用 `docqa,openai`；不要沿用默认的 `docqa,xinghuo`。

仅当用户明确不愿将外部模型密钥配置到讯飞平台，或要求完全自建 RAG 时，才改为应用后端自行检索并调用模型。

## 执行门禁

在生成客户端工程前必须确认以下事实：

- `xfyun_query_services.py` 已查到 SDK 集成可用的接口服务 app 和 scene，或已明确阻塞原因。
- `xfyun_model_manage.py query <sceneId>` 显示大模型配置为 `nlpType=openai`，模型为目标外部模型（如 `deepseek-chat`）。
- `xfyun_knowledge.py docs <libId>` 显示核心知识文档状态为就绪。
- `xfyun_knowledge.py status <sceneId>` 显示 docqa 已关联目标知识库。
- `xfyun_model_manage.py query-interact <sceneId>` 的 `nlpAssistantInfo` 为 `docqa,openai`。

任一项未验证时，不得声称“知识库 + DeepSeek 已接通”。
