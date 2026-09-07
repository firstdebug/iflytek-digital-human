---
name: avatar-model-config
description: >-
  大模型（NLP）配置管理工具。由 avatar-workflow-entry
  路由调用。触发条件：已明确需要操作模型配置（绑定/发布/创建自有模型），而非首次接入或故障排查。
tags:
  - model
  - nlp
  - configuration
  - avatar
priority: high
required_tools:
  - name: bind-model
    description: 绑定模型到场景
  - name: publish-scene
    description: 发布场景配置
optional_tools:
  - name: list-models
    description: 列出可用模型
  - name: check-scene-capability
    description: 检查场景是否具备对话能力
  - name: create-custom-model
    description: 创建自有模型
  - name: query-scene-config
    description: 查询场景配置
---

# avatar-model-config: 模型配置和管理

## ⚙️ 运行位置（从任意项目调用时必读）

本 skill 依赖的平台脚本与配置在固定位置：
- 工具根目录：`${CLAUDE_PLUGIN_ROOT}`（插件安装目录，Claude Code 自动解析为真实路径）
- 脚本 `tools/xfyun_*.py` · 工具注册表 `config/tools.yaml`

正文中的 `python tools/xxx.py`、`config/tools.yaml` 等**相对路径均以该根目录为基准**。
从其他项目目录执行时，先 `cd "${CLAUDE_PLUGIN_ROOT}"` 再运行，或改用绝对路径前缀。
依赖：Python 3.8+ 与 requests/playwright/cryptography；首次使用需浏览器登录（见 avatar-credentials）。

## 定位

管理虚拟人的 NLP 模型配置，包括绑定模型、发布配置、创建自有模型。

**调用时机**:
- 配置智能问答（NLP）功能
- 绑定新模型到场景
- 场景配置后需要发布
- 创建/管理自有模型

---

## 核心功能

### 1. 列出可用模型

```bash
python tools/xfyun_model_manage.py list
```

**输出**:
```
讯飞官方模型:
  - 星火4.0超拟人 (xinghuo-4.0-ultra)
  - 星火4.0 (xinghuo-4.0)
  - 星火3.5 (xinghuo-3.5)

自有模型:
  - 自定义GPT4 (custom-gpt4)
  - 自定义Claude (custom-claude)
```

### 2. 检查场景能力

```bash
python tools/xfyun_model_manage.py check <sceneId>
```

**检查项**:
- ✅ 是否具备对话能力（LLM 授权）
- ✅ 授权的模型列表

**典型问题**: 如果返回无对话能力，说明该场景未授权 LLM，需要换一个有授权的场景或联系平台开通。

### 3. 绑定模型到场景

```bash
python tools/xfyun_model_manage.py bind <sceneId> <modelName>
```

**流程**:
1. 检查场景是否有对话能力
2. 查询现有 NLP 配置
3. 更新模型绑定
4. 配置 NLP 参数（自动识别 xinghuo/openai 类型）

**参数自动配置**:
- `xinghuo` 模型 → `nlpType: xinghuo`
- `openai` 模型 → `nlpType: openai`
- 其他模型 → 根据 API 类型自动判断

**注意**: bind 后必须 publish 才能生效！

### 4. 发布场景配置

```bash
python tools/xfyun_model_manage.py publish <sceneId>
```

**作用**: 使配置生效（必须步骤）

**发布后**:
- ✅ 新的模型绑定生效
- ✅ NLP 参数更新生效
- ✅ sceneId 状态变为"已发布"

**典型错误**: `avatar authentication failed` 往往是忘记 publish。

### 5. 创建自有模型

```bash
python tools/xfyun_model_manage.py create <name> <model> <introduce> <apiUrl>
```

**交互式输入**:
- `apiKey`: 安全输入（不回显）
- 支持从加密文件读取

**示例**:
```bash
# 创建自定义 GPT-4 模型
python tools/xfyun_model_manage.py create \
  "自定义GPT4" \
  "gpt-4" \
  "Azure OpenAI GPT-4" \
  "https://your-azure.openai.azure.com/v1"

# 交互输入 apiKey
```

### 6. 更新模型密钥

```bash
python tools/xfyun_model_manage.py update <modelName>
```

**安全流程**:
1. 交互式输入新 apiKey（不回显）
2. 自动脱敏显示确认
3. 更新到平台
4. 可选：加密保存到本地

### 7. 查询场景配置

```bash
python tools/xfyun_model_manage.py query <sceneId>
```

**输出**:
- NLP 配置（模型、参数）
- 交互配置
- 绑定状态

---

## 决策分支

```
模型配置任务
├── 查看可用模型
│   └── python tools/xfyun_model_manage.py list
│
├── 配置智能问答（NLP）
│   ├── Step 1: 检查场景能力
│   │   └── python tools/xfyun_model_manage.py check <sceneId>
│   │       ├── 有能力 → 继续
│   │       └── 无能力 → 换场景或联系平台
│   │
│   ├── Step 2: 绑定模型
│   │   └── python tools/xfyun_model_manage.py bind <sceneId> <modelName>
│   │
│   └── Step 3: 发布配置（必须！）
│       └── python tools/xfyun_model_manage.py publish <sceneId>
│
├── 使用自有模型
│   ├── 创建模型 → python tools/xfyun_model_manage.py create ...
│   ├── 绑定到场景 → python tools/xfyun_model_manage.py bind ...
│   └── 发布 → python tools/xfyun_model_manage.py publish ...
│
└── 更新模型密钥
    └── python tools/xfyun_model_manage.py update <modelName>
```

---

## 关键约束（HARD-GATE）

1. **绑定后必须发布** — bind 不会自动 publish，必须手动执行
2. **场景需要对话能力** — 检查 `check <sceneId>`，无能力时 bind 会失败
3. **apiKey 安全输入** — create/update 不接受命令行传 apiKey，走交互输入
4. **自有模型需要 API 兼容** — OpenAI 格式或讯飞格式（DeepSeek 走 OpenAI 兼容端点，nlpType=openai）
6. **自有模型挂知识库用 openai 链路** — 绑定 DeepSeek 等自有模型后，知识库调用链第二段必须是 `openai`（`docqa,openai`），不能沿用 `docqa,xinghuo`
5. **发布后才生效** — 所有配置修改后都需要 publish

---

## 典型工作流示例

### 场景 1: 给现有场景配置 NLP

```bash
# 1. 检查场景是否有对话能力
python tools/xfyun_model_manage.py check 330998926062784512

# 输出: ✅ 具备对话能力，已授权模型: xinghuo-4.0, xinghuo-3.5

# 2. 绑定星火4.0
python tools/xfyun_model_manage.py bind 330998926062784512 xinghuo-4.0

# 输出: ✅ 已绑定模型 xinghuo-4.0 并配置 NLP (nlpType: xinghuo)

# 3. 发布配置
python tools/xfyun_model_manage.py publish 330998926062784512

# 输出: ✅ 场景已发布
```

### 场景 2: 使用自有 GPT-4 模型

```bash
# 1. 创建自有模型
python tools/xfyun_model_manage.py create \
  "我的GPT4" \
  "gpt-4" \
  "Azure GPT-4 接口" \
  "https://your-endpoint.openai.azure.com/v1"

# 交互输入: your-azure-api-key

# 输出: ✅ 已创建模型 我的GPT4 (ID: 123456)

# 2. 绑定到场景
python tools/xfyun_model_manage.py bind 330998926062784512 我的GPT4

# 3. 发布
python tools/xfyun_model_manage.py publish 330998926062784512
```

### 场景 2b: 使用 DeepSeek 作为自有模型（外部 LLM 原生接入）

DeepSeek 提供 OpenAI 兼容接口，注册为自有模型后 `nlpType` 自动识别为 `openai`，
可直接当虚拟人对话大脑，也可与知识库组成 `docqa,openai` 链路（见 avatar-knowledge-base）。

```bash
# 1. 创建 DeepSeek 自有模型
#    - <model> 用 DeepSeek 的模型标识，如 deepseek-chat
#    - <apiUrl> 用 OpenAI 兼容端点：https://api.deepseek.com/v1
python tools/xfyun_model_manage.py create \
  "DeepSeek" \
  "deepseek-chat" \
  "DeepSeek OpenAI 兼容接口" \
  "https://api.deepseek.com/v1"

# 交互输入: DeepSeek 的 sk-xxx API Key（不回显，加密存储）
# 输出: ✅ 模型创建成功

# 2. 绑定到场景（nlpType 自动=openai，apiKey/baseUrl 写入 nlpExtra）
python tools/xfyun_model_manage.py bind 330998926062784512 DeepSeek

# 3. 发布
python tools/xfyun_model_manage.py publish 330998926062784512

# 4.（可选）挂知识库：链路第二段必须是 openai
#    python tools/xfyun_knowledge.py enable 330998926062784512 <libId> --chain docqa,openai
```

> **端点注意**：apiUrl 填到 `/v1` 层级（讯飞按 OpenAI 兼容格式拼 `/chat/completions`）。
> model 标识要与 DeepSeek 官方一致（如 `deepseek-chat` / `deepseek-reasoner`），否则调用会 404。

### 场景 3: 查询当前配置

```bash
python tools/xfyun_model_manage.py query 330998926062784512

# 输出:
# NLP 配置:
#   模型: xinghuo-4.0
#   nlpType: xinghuo
#   参数: {...}
```

---

## 错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| bind 被拒绝 | 场景无对话能力 | 用 `check` 查授权，换有能力的场景 |
| 配置不生效 | 忘记 publish | 运行 `publish <sceneId>` |
| authentication failed | sceneId 未发布 | 运行 `publish <sceneId>` |
| 自有模型 API 调用失败 | apiKey 错误或 API 不兼容 | 用 `update` 更新密钥 |
| create 后 apiKey 是空 | 交互输入被跳过 | 重新运行 create 并完整输入 |

---

## 安全约束

- ✅ **apiKey 不进命令行** — create/update 走交互输入
- ✅ **自动脱敏显示** — 确认时只显示前后缀
- ✅ **可选加密存储** — 保存到 `<plugin-root>/.runtime/secrets/secrets.enc`
- ✅ **debug 输出过滤** — 日志不包含完整密钥

---

## 验证清单

- [ ] 场景具备对话能力（check 通过）
- [ ] 模型已绑定到场景
- [ ] NLP 参数已配置（nlpType 正确）
- [ ] 场景已发布（publish 执行）
- [ ] 测试对话功能正常

---

## 相关技能

- `avatar-credentials`: 获取 sceneId 等凭据
- `avatar-troubleshoot`: 排查 authentication failed 等问题（运行时案例）
- `text-interact`: 使用配置好的 NLP 功能
