# 知识库命令与操作细节

## 目录

- [命令表](#命令表)
- [创建知识库](#创建知识库)
- [上传与检查文档](#上传与检查文档)
- [关联场景](#关联场景)
- [分类与版本](#分类与版本)
- [更新调用链](#更新调用链)
- [删除操作](#删除操作)
- [端到端验证](#端到端验证)

所有命令都在 `<plugin-root>` 执行。尖括号内容必须由平台查询或用户输入提供。

## 命令表

| 任务 | 命令 |
|---|---|
| 列出知识库 | `python tools/xfyun_knowledge.py list` |
| 列出标签 | `python tools/xfyun_knowledge.py labels` |
| 列出可用模型 | `python tools/xfyun_knowledge.py models` |
| 创建标签 | `python tools/xfyun_knowledge.py create-label <name>` |
| 创建知识库 | `python tools/xfyun_knowledge.py create-kb <name> [options]` |
| 上传文档 | `python tools/xfyun_knowledge.py upload <libId> <files...> [options]` |
| 查看文档 | `python tools/xfyun_knowledge.py docs <libId>` |
| 查看版本 | `python tools/xfyun_knowledge.py versions <libId>` |
| 查看分类 | `python tools/xfyun_knowledge.py categories <libId>` |
| 创建分类 | `python tools/xfyun_knowledge.py create-category <libId> <name>` |
| 启用知识库 | `python tools/xfyun_knowledge.py enable <sceneId> <libId> [--chain <chain>]` |
| 禁用知识库 | `python tools/xfyun_knowledge.py disable <sceneId>` |
| 修改链路 | `python tools/xfyun_knowledge.py chain <sceneId> <chain>` |
| 查询场景状态 | `python tools/xfyun_knowledge.py status <sceneId>` |
| 发布场景 | `python tools/xfyun_knowledge.py publish <sceneId>` |
| 删除文档 | `python tools/xfyun_knowledge.py delete-doc <docId>` |
| 删除知识库 | `python tools/xfyun_knowledge.py delete-kb <libId>` |

## 创建知识库

```bash
python tools/xfyun_knowledge.py labels
python tools/xfyun_knowledge.py create-label "<labelName>"
python tools/xfyun_knowledge.py create-kb "<knowledgeBaseName>" \
  --label <labelId> --desc "<description>"
```

可选向量模型和 LLM 参数以 `models` 的实际查询结果为准，不把文档中的示例模型名当成账号授权结果。记录返回的 `libId`。

## 上传与检查文档

普通文档：

```bash
python tools/xfyun_knowledge.py upload <libId> <documentPath> --wait
```

多个文件可在一次命令中连续传入。常用选项：

| 选项 | 用途 |
|---|---|
| `--wait` | 等待处理完成 |
| `--split 7` | 智能拆分，普通文档默认选择 |
| `--split 3` | 按自动目录拆分 |
| `--split 9` | 使用自定义目录 |
| `--split 2` | 按分隔符拆分 |
| `--split 5` | 整篇不拆分 |
| `--file-type qa` | 上传问答对表格 |
| `--category <categoryId>` | 归入已存在分类 |

上传后查询：

```bash
python tools/xfyun_knowledge.py docs <libId>
```

只有目标文档 `status=1` 且段落数大于 0 才视为处理完成。失败项应单独重传并保留平台错误信息。

## 关联场景

官方星火模型：

```bash
python tools/xfyun_knowledge.py enable <sceneId> <libId> --chain docqa,xinghuo
python tools/xfyun_knowledge.py publish <sceneId>
```

OpenAI 兼容自有模型：

```bash
python tools/xfyun_knowledge.py enable <sceneId> <libId> --chain docqa,openai
python tools/xfyun_knowledge.py publish <sceneId>
```

然后查询：

```bash
python tools/xfyun_knowledge.py status <sceneId>
```

## 分类与版本

```bash
python tools/xfyun_knowledge.py categories <libId>
python tools/xfyun_knowledge.py create-category <libId> "<categoryName>"
python tools/xfyun_knowledge.py create-category <libId> "<childName>" --parent <parentId>
python tools/xfyun_knowledge.py versions <libId>
```

分类 ID 只在所属知识库内使用。上传新文档后检查新版本及文档状态；单纯内容更新通常不要求重新发布场景。

## 更新调用链

先查询当前模型类型和链路，再修改并发布：

```bash
python tools/xfyun_model_manage.py query <sceneId>
python tools/xfyun_knowledge.py status <sceneId>
python tools/xfyun_knowledge.py chain <sceneId> <chain>
python tools/xfyun_knowledge.py publish <sceneId>
```

模型优先的链路可选 `xinghuo,docqa` 或 `openai,docqa`。修改模型后必须重新确认 `docqa` 仍在链路中。

## 删除操作

删除文档时使用 `docs` 返回的 `docId`，不是上传接口内部的文件标识：

```bash
python tools/xfyun_knowledge.py delete-doc <docId>
python tools/xfyun_knowledge.py delete-kb <libId>
```

脚本会对不可逆删除进行确认。删除整个知识库会连带删除库内文档和分类。

## 端到端验证

1. `docs` 确认目标文档处理成功。
2. `status` 确认场景关联了正确知识库和链路。
3. 用文档中有唯一答案的问题发起真实对话。
4. 核对回答确实使用文档信息，而非仅凭通用模型知识。
5. 再用文档外问题确认回退策略符合链路设计。
