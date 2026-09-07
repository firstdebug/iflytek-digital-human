---
name: avatar-knowledge-base
description: >-
  知识库（docqa/RAG）管理工具。由 avatar-workflow-entry
  路由调用。触发条件：已明确要操作知识库（创建/上传文档/关联场景/配置检索），而非首次规划。
tags:
  - knowledge
  - docqa
  - rag
  - nlp
  - avatar
priority: high
required_tools:
  - name: xfyun_knowledge.py create-kb
    description: 创建知识库
  - name: xfyun_knowledge.py upload
    description: 上传文档
  - name: xfyun_knowledge.py enable
    description: 启用知识库对话
optional_tools:
  - name: xfyun_knowledge.py list
    description: 列出已有知识库
  - name: xfyun_knowledge.py labels
    description: 列出标签
  - name: xfyun_knowledge.py models
    description: 列出可用模型
  - name: xfyun_knowledge.py create-category
    description: 创建知识库分类（顶级或子分类）
  - name: xfyun_knowledge.py delete-doc
    description: 删除文档
  - name: xfyun_knowledge.py delete-kb
    description: 删除知识库
  - name: xfyun_knowledge.py status
    description: 查询场景知识库状态库状态
  - name: xfyun_knowledge.py docs
    description: 查询知识库文档
---

# avatar-knowledge-base: 知识库管理

## ⚙️ 运行位置（从任意项目调用时必读）

本 skill 依赖的平台脚本与配置在固定位置：
- 工具根目录：`${CLAUDE_PLUGIN_ROOT}`（插件安装目录，Claude Code 自动解析为真实路径）
- 脚本 `tools/xfyun_*.py` · 工具注册表 `config/tools.yaml`

正文中的 `python tools/xxx.py`、`config/tools.yaml` 等**相对路径均以该根目录为基准**。
从其他项目目录执行时，先 `cd "${CLAUDE_PLUGIN_ROOT}"` 再运行，或改用绝对路径前缀。
依赖：Python 3.8+ 与 requests/playwright/cryptography；首次使用需浏览器登录（见 avatar-credentials）。

## 定位

管理虚拟人的知识库（docqa）功能，支持 RAG（检索增强生成）对话。

**调用时机**:
- 虚拟人需要基于文档回答问题
- 配置领域知识库（产品手册、FAQ等）
- 上传/更新知识库文档
- 关联知识库到场景

**前置条件**:
- 场景必须具备对话能力（LLM 授权）
- 需要先绑定 NLP 模型（见 `avatar-model-config`）——**可以是官方星火，也可以是自有模型（如 DeepSeek）**
- 绑的是自有模型时，记住其 nlpType 为 `openai`，后续 `enable`/`chain` 用 `docqa,openai`

---

## 核心概念

### 知识库（docqa）

虚拟人的知识库系统，支持：
- ✅ 上传文档（PDF/Word/Markdown/TXT等）
- ✅ 自动拆分、向量化
- ✅ 对话时检索相关段落
- ✅ LLM 基于检索结果生成回答

### 调用链（chain）

决定虚拟人回答问题的流程:
- `docqa,xinghuo` — 先查知识库，再用**星火**生成答案（官方模型时推荐）
- `docqa,openai` — 先查知识库，再用**自有模型（DeepSeek/GPT 等，nlpType=openai）**生成答案
- `xinghuo,docqa` — 先让星火回答，再补充知识库
- `docqa` — 只用知识库
- `xinghuo` / `openai` — 只用 LLM（无知识库）

**调用链第二段 = 场景当前绑定的大模型 nlpType**：官方星火→`xinghuo`；自有模型（DeepSeek 等）→`openai`。
如果场景绑的是 DeepSeek 自有模型，务必用 `docqa,openai`，否则 `docqa,xinghuo` 会把检索结果喂给星火而非 DeepSeek。

---

## 核心工作流

### 完整配置流程

```
创建知识库 → 上传文档 → 等待处理 → 关联并发布 → 验证 → 测试
     ↓           ↓          ↓           ↓          ↓       ↓
  create-kb   upload      --wait      enable      status  对话测试
```

### 1. 创建知识库

```bash
# 列出标签
python tools/xfyun_knowledge.py labels

# 创建标签（如果需要）
python tools/xfyun_knowledge.py create-label "产品文档"

# 创建知识库
python tools/xfyun_knowledge.py create-kb "我的知识库" \
  --label <labelId> \
  --desc "产品使用手册" \
  --vector emb_v1_1024 \
  --llm xhdmx1

# 输出: 知识库ID (libId)
```

### 2. 上传文档

```bash
# 上传单个文档
python tools/xfyun_knowledge.py upload <libId> ./manual.pdf --wait

# 上传多个文档
python tools/xfyun_knowledge.py upload <libId> ./doc1.md ./doc2.pdf --wait

# 指定拆分策略
python tools/xfyun_knowledge.py upload <libId> ./doc.md --split 7 --wait

# 上传问答对 Excel（第一列=问题，第二列=答案）
python tools/xfyun_knowledge.py upload <libId> ./qa.xlsx --file-type qa --wait

# --wait 参数会等待文档处理完成（拆分、向量化）
```

**支持格式**:
- PDF
- Word (doc/docx)
- Markdown
- 纯文本
- Excel (csv/xlsx，含问答对模板)

**拆分策略（splitType）**:
- `7` - 智能拆分（默认，推荐普通文章/说明书）
- `3` - 自动目录（有明确章节的文档）
- `9` - 自定义目录（自定义标题格式）
- `2` - 分隔符拆分（纯 Q&A 对话格式）
- `5` - 不拆分（整篇作为一个知识单元）

**文档类型（fileType）**:
- `text` - 普通文档（默认）
- `qa` - 问答对 Excel 模板（.xlsx，第一列=问题，第二列=答案）

### 3. 查看文档处理状态

```bash
# 查看知识库的文档列表
python tools/xfyun_knowledge.py docs <libId>

# 输出:
# 文档ID  名称        状态         段落数
# 123    manual.pdf  1(就绪)      58
# 124    faq.md      -2(处理中)   0
```

**状态说明**:
- `1` — 就绪
- `0` / `-2` / `-4` — 处理中
- `-3` — 采编异常

### 4. 关联场景

```bash
# 为场景启用知识库对话（官方星火模型）
python tools/xfyun_knowledge.py enable <sceneId> <libId>

# 为场景启用知识库对话（自有模型，如 DeepSeek）—— 必须显式指定 openai 链路
python tools/xfyun_knowledge.py enable <sceneId> <libId> --chain docqa,openai

# `enable` 默认会自动:
# 1. 设置调用链（默认 "docqa,xinghuo"；自有模型用 --chain docqa,openai）
# 2. 配置 nlpExtra.domain
# 3. 关联知识库
# 4. 发布场景配置
```

### 5. 仅在显式延迟发布时单独发布

```bash
# 只有此前使用 enable --no-publish，或单独执行 disable/chain 后，才需显式发布
python tools/xfyun_knowledge.py publish <sceneId>
```

### 6. 查询状态

```bash
# 查看场景当前的知识库配置
python tools/xfyun_knowledge.py status <sceneId>

# 输出:
# 知识库: 我的知识库 (lib_abc123)
# 调用链: docqa,xinghuo
# 状态: 已启用
```

### 7. 管理分类

```bash
# 查看某库的分类
python tools/xfyun_knowledge.py categories <libId>

# 创建顶级分类
python tools/xfyun_knowledge.py create-category <libId> "产品文档"
# 输出: categoryId=cat_xxx

# 创建子分类（--parent 指定父分类 id）
python tools/xfyun_knowledge.py create-category <libId> "常见问题" --parent cat_xxx
```

分类用于文档归类；上传时用 `--category <id>` 指定归属（不指定则用默认分类）。

### 8. 删除操作（不可逆，需二次确认）

```bash
# 删除文档（docId 从 docs 命令获取，不是 fileID）
python tools/xfyun_knowledge.py delete-doc <docId>
# 需输入 yes 确认

# 删除整个知识库（含所有文档）
python tools/xfyun_knowledge.py delete-kb <libId>
# 需输入库 ID 确认
```

⚠️ 删除不可逆。删库会连带删除库内所有文档和分类，操作前务必确认。

---

## 决策分支

```
知识库管理任务
├── 新建知识库
│   ├── 列出标签 → python tools/xfyun_knowledge.py labels
│   ├── 创建标签（如需要）→ create-label
│   ├── 创建知识库 → create-kb
│   └── 记录 libId
│
├── 上传文档
│   ├── 单个文档 → upload <libId> <filepath> --wait
│   ├── 批量上传 → 循环调用 upload
│   └── 查看状态 → docs <libId>
│
├── 关联场景
│   ├── 检查场景对话能力 → avatar-model-config check
│   ├── 启用知识库 → enable <sceneId> <libId>
│   └── 发布 → publish <sceneId>
│
├── 调整配置
│   ├── 修改调用链 → chain <sceneId> <chain>
│   ├── 禁用知识库 → disable <sceneId>
│   └── 重新发布 → publish <sceneId>
│
└── 查询与排障
    ├── 列出所有知识库 → list
    ├── 查看场景状态 → status <sceneId>
    ├── 查看文档列表 → docs <libId>
    └── 查看版本 → versions <libId>
```

---

## 关键约束（HARD-GATE）

1. **文档处理需要时间** — 上传后需等待拆分、向量化（用 `--wait` 或手动查询）
2. **启用默认自动发布** — `enable` 默认包含 `publish`；只有传入 `--no-publish` 才需稍后手动发布
3. **场景需要对话能力** — 无 LLM 授权时 `enable` 会失败
4. **调用链顺序影响效果** — `docqa,xinghuo` 优先知识库，`xinghuo,docqa` 优先 LLM
5. **换模型会重置调用链** — 如果用 `avatar-model-config bind` 换模型，`nlpAssistantInfo` 会被重写为该模型的 nlpType（自有模型→`openai`），需重新 `enable` 或 `chain` 把 docqa 加回，且第二段要用新模型的 nlpType（如 `docqa,openai`）
7. **自有模型链路段是 openai** — DeepSeek/GPT 等自有模型绑定后，`enable`/`chain` 必须用 `docqa,openai`，用 `docqa,xinghuo` 会把检索结果喂给星火（若场景无星火授权还会报错）
6. **分类必须存在** — 上传时指定的 `--category` 必须是已存在的分类ID

---

## 典型工作流示例

### 场景 1: 创建产品知识库

```bash
# 1. 创建标签
python tools/xfyun_knowledge.py create-label "产品手册"
# 输出: labelId=L123

# 2. 创建知识库
python tools/xfyun_knowledge.py create-kb "产品知识库" \
  --label L123 \
  --desc "包含所有产品使用手册和FAQ"
# 输出: libId=lib_abc123

# 3. 上传文档
python tools/xfyun_knowledge.py upload lib_abc123 ./产品手册.pdf --wait
python tools/xfyun_knowledge.py upload lib_abc123 ./FAQ.md --wait
# 输出: 文档已上传并处理完成，共58段落

# 4. 关联场景
python tools/xfyun_knowledge.py enable 330998926062784512 lib_abc123
# 输出: ✅ 已启用知识库对话，调用链: docqa,xinghuo

# 5. 测试对话（enable 已默认发布）
# 用户问: "如何重置密码？"
# 虚拟人会从 FAQ.md 中检索相关段落并生成回答
```

### 场景 2: 查看已有知识库并关联

```bash
# 1. 列出所有知识库
python tools/xfyun_knowledge.py list

# 输出:
# ID              名称          标签      文档数  状态
# lib_abc123      产品知识库    产品手册   15     启用
# lib_def456      FAQ库        FAQ        8      启用

# 2. 查看某个知识库的文档
python tools/xfyun_knowledge.py docs lib_abc123

# 3. 关联到新场景
python tools/xfyun_knowledge.py enable 新场景ID lib_abc123
```

### 场景 3: 更新知识库内容

```bash
# 1. 上传新文档
python tools/xfyun_knowledge.py upload lib_abc123 ./新版手册.pdf --wait

# 2. 查看版本
python tools/xfyun_knowledge.py versions lib_abc123
# 输出: 版本2（新）包含16个文档，版本1（旧）包含15个文档

# 3. 无需重新发布（版本自动生效）
# 但如果修改了调用链或关联，需要 publish
```

### 场景 4: 调整调用链

```bash
# 场景: 想让 LLM 先回答，知识库作为补充

# 1. 查看当前配置
python tools/xfyun_knowledge.py status 330998926062784512
# 输出: 调用链: docqa,xinghuo

# 2. 修改调用链
python tools/xfyun_knowledge.py chain 330998926062784512 "xinghuo,docqa"

# 3. 发布
python tools/xfyun_knowledge.py publish 330998926062784512

# 现在虚拟人会先用 LLM 回答，再补充知识库内容
```

### 场景 5: 健身知识库 + DeepSeek 自有模型（外部 LLM 原生集成）

```bash
# 前提：DeepSeek 已注册为自有模型并绑定到场景（见 avatar-model-config）
#      绑定后场景的大模型 nlpType = openai

# 1. 建标签 + 建库
python tools/xfyun_knowledge.py create-label "健身知识"
python tools/xfyun_knowledge.py create-kb "健身知识库" --label <labelId> --desc "健身动作/训练/营养知识"
# 输出: libId=lib_fitness

# 2. 上传健身文档（平台自动切块+向量化）
python tools/xfyun_knowledge.py upload lib_fitness ./健身知识1.md ./健身知识2.md --wait

# 3. 关联场景，链路指向 DeepSeek（openai），不是星火！
python tools/xfyun_knowledge.py enable <sceneId> lib_fitness --chain docqa,openai
# 输出: ✅ 已启用知识库对话，调用链: docqa,openai

# 4. 校验
python tools/xfyun_knowledge.py status <sceneId>
# 用户问"深蹲怎么做" → 先检索健身知识库 → 检索结果喂给 DeepSeek 生成答案
```

---

## 错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| 文档一直"处理中(段落0)" | 拆分时 categoryID 为空 | 重传文档，用工具默认分类或 `--category` 指定 |
| 对话不引用知识库 | 调用链没含 docqa | 跑 `enable`，或 `chain <sceneId> docqa,xinghuo` |
| 换模型后知识库失效 | bind 重置了调用链 | 换模型后重跑 `enable` 把 docqa 加回，第二段用新模型 nlpType |
| 挂了 DeepSeek 但回答不对/报错 | 链路用了 `docqa,xinghuo`，检索结果喂给星火而非 DeepSeek | 重跑 `enable <sceneId> <libId> --chain docqa,openai` |
| 对话报 domain can not be blank | nlpExtra domain 为空 | 重跑 `enable/bind` 补全 domain |
| enable 失败 | 场景无对话能力 | 用 `avatar-model-config check` 查授权 |
| 文档处理失败 | 格式不支持或文件损坏 | 检查文件格式，重新上传 |

---

## 安全约束

- ✅ **文档内容不进对话框** — 工具直接上传到平台
- ✅ **libId 自动生成** — 无需手动管理
- ✅ **版本自动管理** — 每次上传文档创建新版本

---

## 调用链推荐

| 场景 | 推荐调用链 | 说明 |
|------|-----------|------|
| 严格基于文档回答 | `docqa` | 只用知识库，不用 LLM |
| 知识库优先（官方星火） | `docqa,xinghuo` | 先检索知识库，再用星火生成答案 |
| 知识库优先（自有模型 DeepSeek/GPT） | `docqa,openai` | 先检索知识库，再用自有模型生成答案 |
| LLM 优先 | `xinghuo,docqa` / `openai,docqa` | 先 LLM 回答，再补充知识库 |
| 无知识库 | `xinghuo` / `openai` | 只用 LLM，不检索知识库 |

> 链路第二段必须与场景实际绑定的模型 nlpType 一致：官方=`xinghuo`，自有（DeepSeek 等）=`openai`。

---

## 验证清单

- [ ] 知识库已创建（有 libId）
- [ ] 文档已上传并处理完成（status=1，段落数>0）
- [ ] 场景具备对话能力（check 通过）
- [ ] 知识库已关联场景（enable 执行）
- [ ] 调用链已配置（包含 docqa）
- [ ] 配置已发布（enable 默认发布；使用 --no-publish 时已补执行 publish）
- [ ] 测试对话引用知识库内容

---

## 相关技能

- `avatar-model-config`: 配置 NLP 模型（知识库的前置条件）
- `avatar-credentials`: 获取 sceneId 等凭据
- `text-interact`: 使用配置好的知识库对话
- `avatar-troubleshoot`: 排查对话问题（含运行时案例）
