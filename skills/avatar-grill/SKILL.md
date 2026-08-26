---
name: avatar-grill
description: 通过证据驱动的集中访谈完成讯飞虚拟人需求确认，并在用户确认执行契约后直接创建、配置、排障或验证 Web、Android、iOS、WebAPI、模板、直播、模型和知识库任务。用于任何 xfyun 虚拟人或数字人请求。
---

# Avatar Grill

## 定位

这是讯飞虚拟人任务的单一入口和执行器。不要把用户转交给其他 Skill，也不要要求用户选择流程模式。

始终按同一个状态机工作：

```text
识别目标 -> 查询事实 -> 计算问题前沿 -> 集中提问 -> 确认执行契约
         -> 直接执行 -> 确定性验证 -> 修复或交付
```

确定插件根目录：

- Claude 使用宿主提供的 `${CLAUDE_PLUGIN_ROOT}`。
- Codex/Cursor 使用包含 `tools/`、`config/`、`skills/` 的插件仓库根目录。
- 先检查 `<repo-root>/tools/xfyun_common.py`；不存在就停止并报告安装方式错误。
- 禁止扫描其他安装目录、cache、backup 或同名旧插件。

- 平台工具：`<repo-root>/tools/`
- 平台配置：`<repo-root>/config/`
- 内置领域资料：`references/modules/`
- 契约校验器：`scripts/validate_contract.py`

只使用当前仓库中的资料。不要扫描其他安装目录、缓存、备份或同名 Skill。

## 不可违反的边界

1. 用户决定需求；工具提供平台事实。不得让用户提供或确认本可由工具查询的事实。
2. WebSocket 地址只能来自 `tools/platform_endpoints.py`，当前固定值为
   `wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`。不得询问、猜测或拼接地址。
3. appId、appType、sceneId、发布状态、资源授权和可用 SDK 必须由工具或实际产物验证。
4. apiKey、apiSecret、Cookie、模型密钥不得进入对话、执行契约、日志或版本库。
5. 未经用户明确确认，不得新增录音、麦克风权限、语音交互或不可逆的平台写操作。
6. 不凭记忆生成 SDK API。Web 读取实际 `index.d.ts`；Android 读取实际 AAR 或内置实测 Playbook；iOS 读取实际 framework/header。
7. 中间失败是同一任务的可恢复状态。执行修复并复验；只有确定性完成证据通过才交付。
8. 不用设计文档、计划文档或评审报告代替工程、平台操作与运行验证。

## 阶段 0：隐私授权

如果宿主注入 `[avatar-grill consent] status=<accepted|declined|undecided|stale>`：

- `accepted`：继续，不重复询问。
- `declined`：保持统计关闭并继续，不重复提示。
- `undecided` 或 `stale`：运行 `python "<repo-root>/tools/telemetry.py" notice`，原样展示声明并等待用户明确同意或不同意。

没有注入状态时，静默运行：

```bash
python "<repo-root>/tools/telemetry.py" consent --status
```

只有明确同意才运行 `consent --accept`；明确拒绝运行 `consent --decline`。授权不影响业务能力是否可用，统计失败也不能阻塞任务。

首次同意后必须重新读取本入口，形成授权后的真实 `read` invocation，再异步执行一次 `python "<repo-root>/tools/uploader.py" --force`。不得追溯写入授权前的 prompt 或 slash；拒绝时不重新读取入口，也不运行上传器。

## 阶段 1：识别任务

先扫描用户指定的工程或当前工程，只做只读检查。把任务归入 [能力与执行](references/capability-execution.md) 中的一个或多个 `task.kind`：

- `docs`
- `sdk_build`、`sdk_extend`
- `web_template`、`live_streaming`、`webapi`
- `credentials`、`resource_management`
- `model_config`、`knowledge_base`
- `configuration`、`permissions`
- `diagnose`、`verify`

故障信号优先于创建和配置。用户只咨询时不得擅自修改工程或平台。

## 阶段 2：先查询事实

读取 [工具与证据](references/tool-and-evidence-map.md)，先取得当前任务需要的事实：

- 工程路径、平台、现有 SDK 和当前改动
- 登录状态和账号下的应用
- appId 的 appType、授权能力和完整凭据是否可安全取得
- sceneId 所属 appId、sceneType、发布状态和 NLP/知识库配置
- avatarId、vcn、SDK 产物和工具链
- 已有构建、运行、浏览器和交付证据

工具需要扫码、授权或人工视觉/听觉确认时，才把对应动作交给用户。

## 阶段 3：Grill

读取 [问题树](references/question-tree.md)，建立依赖树并计算当前 `frontier`：所有前置条件已满足、但答案仍未知且会改变执行路径的问题。

- 严格使用问题树中的 `❓ Qn` / `➡️ 推荐` / 分隔线格式，一轮集中询问当前全部 frontier；等用户整轮回答后再重算。
- 每个问题给出推荐答案及影响。
- 不问已经由用户回答、工程扫描得到或工具验证过的内容。
- 用户回答后重新计算 frontier；没有新的必要问题就停止询问。
- 不为了“更完整”询问不会改变实现的偏好。
- `docs` 咨询的 frontier 为空时直接回答，不生成写操作契约。
- 未选择语音时，把语音、全双工和相关麦克风能力写入 `features.excluded`，不额外追问是否顺便加入。

## 阶段 4：执行契约

根据 [执行契约](references/execution-contract.md) 在目标工程写入：

```text
.avatar/avatar-run-contract.json
```

契约必须记录每个关键值的 `source` 和 `verified`，同时记录启用能力、明确排除项、验收条件与用户确认状态。不得写入任何密钥。

校验：

```bash
python "<repo-root>/skills/avatar-grill/scripts/validate_contract.py" \
  "<project>/.avatar/avatar-run-contract.json"
```

先向用户展示紧凑摘要并等待一次明确确认。确认前只允许只读查询、登录、下载和校验，不得创建项目、修改工程、发布场景或上传知识库。

用户确认后把 `confirmation.confirmed` 设为 `true`，再次校验，然后进入执行。后续不得用模型推断覆盖已验证参数；物料事实变化时更新来源并重新校验，需求边界变化时重新确认受影响部分。

## 阶段 5：直接执行

按 [能力与执行](references/capability-execution.md) 的 `task.kind` 选择资料，只读取该行列出的模块、工具和证据规则。内置 `source-skill.md` 只作为领域事实来源；不得把资料文件当作入口或第二套流程。

执行原则：

- 主 Agent 完成可以自动完成的命令、代码、构建、服务启动和测试。
- 写平台数据前确认契约授权了该动作；删除等不可逆操作在执行前再次取得用户批准。
- 平台工具返回结构化失败时读取错误和 `next_action`，执行修复后重试同一任务。
- 同一个阻塞连续修复两次仍无新证据时停止重试，报告证据和恢复条件。
- 保留用户已有改动，不清理无关文件。
- 写代码前先读取对应平台 Playbook 全文；Web 读取实际 `index.d.ts`，Android/iOS 读取真实 SDK 产物或 Playbook。
- 写完按平台黑名单检查 API，构建、运行和资源查询的退出码及副作用必须真实存在。

## 阶段 6：验证与完成

读取 [平台门禁](references/platform-gates.md)。最低要求：

- SDK 工程：配置、安全、构建、启动、连接、首帧和目标交互均有证据。
- Web SDK：只用 `web_delivery.py run` 编排凭据、签名、SDK、服务、浏览器证据与最终门禁。
- Android：串行 Gradle，在线预热后离线复验；命令超时先检查原进程。
- 平台资源：重新查询确认创建、绑定、发布或关联结果已经生效。
- 故障修复：复现证据消失且回归链路通过。

完成证据写入目标工程：

- SDK/本地工程：`.runtime/verification-result.json`
- 模板、直播、知识库等平台交付：`.runtime/artifacts.json`
- 凭据配置：安全写入 `.env`，只记录键存在性，不记录值

只有门禁明确返回 `ready_to_deliver: true` 才标记完成。`ready_to_deliver: false` 默认仍可恢复；只有明确的 `terminal_failure: true` 才是失败终态。

如果统计授权已同意，在最终响应前用真实项目路径同步完成状态；命令失败不得阻塞交付：

```bash
python "<repo-root>/tools/telemetry.py" complete \
  --project "<project>" --type "<workflow-type>"
```

`workflow-type` 映射：SDK 创建/扩展/验证=`sdk_integration`，模板=`web_template`，直播=`live_streaming`，WebAPI=`webapi_protocol`，凭据/资源=`credentials_setup`，模型=`model_config`，知识库=`knowledge_base`，配置=`config_authoring`，排障=`troubleshoot`。只有明确终止且不可恢复时才运行 `telemetry.py fail`；普通阻塞和待用户交互不标失败。

## 最终响应

只给出：完成内容、可运行位置或平台产物、验证证据、仍存在的外部阻塞。不要输出过程报告，也不要声称无法实际验证的内容已经通过。
