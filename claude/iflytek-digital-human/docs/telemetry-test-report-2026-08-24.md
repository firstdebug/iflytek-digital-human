# Avatar Telemetry 分章节测试报告

> 历史测试证据：本报告是 2026-08-24 SQLite 版本的实测记录，不代表当前本地存储实现。JSON 状态机当前验证结果见 [telemetry-architecture-and-validation.md](telemetry-architecture-and-validation.md)。

测试日期：2026-08-24
测试对象：Claude Code iflytek-digital-human Skill telemetry 及 Zhisheng 后端接收、落库链路
平台范围：Web、Android 及通用 WebAPI/Skill 场景；按约定不包含 iOS
后端数据库：`yousheng_interaction_platform`
上报接口：`POST /zs_admin/avatarTelemetry/report`

## 一、测试范围与判定口径

本报告把测试分为四类：

1. **代码正确性与幂等测试**：验证重复上报、ACK、revision、失败重试、死信、并发锁、数据库重建等分支。
2. **真实场景测试**：从真实 Claude Code 会话或真实 HTTP 请求出发，分别验证正常完成和出现问题时的记录结果。
3. **代码完整性测试**：验证客户端全部 Python 测试、后端 telemetry 定向测试、构建产物和数据库字段对账。
4. **昨日历史结果**：保留并纳入昨日真实会话的结果，不删除原始测试数据。

“通过”表示当前本地源码和本地运行环境下达到预期；不等同于生产网关、正式 endpoint 和正式隐私配置已经完成。

## 二、代码正确性与幂等测试

### 2.1 客户端本地队列与上传状态

| 测试场景 | 预期结果 | 实际结果 | 结论 |
|---|---|---|---|
| 首次写入 workflow/invocation | 本地 SQLite 生成待上传记录 | 记录成功生成 | 通过 |
| 正常上传并收到 ACK | 仅 ACK 对应 revision，记录变为 uploaded | `pending=0`，记录已上传 | 通过 |
| 同一 workflow 重放 | 不新增重复 workflow | 重放后仍为 1 条 | 通过 |
| 同一 `(workflow_id, skill_name)` 重放 | 不新增重复 invocation | 重放后无重复 | 通过 |
| 旧 revision ACK 晚到 | 不能确认新 revision | 旧 ACK 未覆盖新 revision | 通过 |
| 网络失败 | 不误标记 uploaded，保留 pending | 失败后仍待上传 | 通过 |
| 网络恢复 | 重新上传并 ACK | 恢复后队列排空 | 通过 |
| 永久拒绝 | 不再无限重试，进入 dead letter | `dead_letter=1` | 通过 |
| 可重试拒绝 | 保留 pending，并按退避时间重试 | 退避未到期不重试，到期可恢复 | 通过 |
| 501 条批次 | 服务端最多处理 500 条，多余项被明确拒绝 | 500 accepted，1 条 `batch_too_large` | 通过 |
| SQLite 文件损坏 | 旧文件隔离并自动重建 schema | 文件改名为 `.corrupt`，数据库恢复可用 | 通过 |

### 2.2 uploader 并发与进程异常

| 测试场景 | 预期结果 | 实际结果 | 结论 |
|---|---|---|---|
| 同时启动两个 uploader | 只能有一个持有进程锁 | 第二实例返回 `uploader already running` | 通过 |
| 持锁进程被杀掉 | 锁不能永久阻塞后续上传 | 新 uploader 可重新获得锁 | 通过 |
| 上传中进程退出 | 未 ACK 的记录仍可继续上传 | 后续实例继续 drain | 通过 |

### 2.3 workflow 生命周期与接续

| 测试场景 | 预期结果 | 实际结果 | 结论 |
|---|---|---|---|
| 正常开始并完成 | workflow 有开始、结束、完成证据 | 状态和完成方法齐全 | 通过 |
| 会话中断后在窗口内重连 | 新 session 复用原 workflow_id | 接续成功，未拆成两条任务 | 通过 |
| 超过接续窗口 | 创建新的 workflow | 未错误合并 | 通过 |
| 前一 workflow 已有 completion evidence | 不再接续到已交付任务 | 终态任务保持独立 | 通过 |
| cancelled | 保留 cancelled 终态及结束时间 | 后端能正常接收并落库 | 通过 |
| completion evidence 过期或失败 | 不能把失败伪装成完成 | 失败证据不会触发完成方法 | 通过 |

### 2.4 后端接口幂等与事务边界

| 请求场景 | 预期返回/落库行为 | 实际结果 |
|---|---|---|
| 空报文 `{}` | HTTP 200，accepted/rejected 为空，不写库 | 符合 |
| privacy version 错误 | `privacy_consent_required`，不写库 | 符合 |
| anonymousId 不匹配 | `anonymousId_mismatch`，不写库 | 符合 |
| revision=0 | `revision_invalid`，不写库 | 符合 |
| 合法记录 + 非法记录混合 | 合法记录接受，非法记录逐条拒绝 | 只写入合法记录 |
| 合法 workflow 重放 | 接口可重复调用，数据库不重复 | 重放后仍只有一条 |
| 501 条合法 workflow | 接受前 500 条，超限项返回 `batch_too_large` | 符合 |
| 501 条非法 workflow | 非法项不写库，超限项单独返回批次错误 | 符合 |

MySQL 对账结果：

```text
重复 workflow                         0
重复 (workflow_id, skill_name)        0
孤儿 invocation                       0
anonymous_id 不一致                   0
非法 status                           0
非法 revision                         0
终态缺 ended_at                       0
时间先后颠倒                          0
completed 缺 completion_method        0
```

### 2.5 本章结论

客户端队列、uploader、workflow 接续、后端校验和数据库唯一性均达到设计预期。重复请求不会造成重复 workflow 或 invocation；网络、进程和数据库异常不会导致已确认数据丢失或错误确认。

## 三、真实场景测试

### 3.1 正常完成场景

测试链路：

```text
Claude Hook -> tracker.py -> SQLite -> uploader.py
-> POST /zs_admin/avatarTelemetry/report -> MySQL
```

实际结果：

- workflow：1 条，`uploaded=1`，`dead_letter=0`。
- invocation：2 条，均 `uploaded=1`。
- MySQL：1 条 workflow、2 条 invocation。
- 重放同一 revision 后数据库数量不增加。
- 本地队列最终 `pending=0`、`dead_letter=0`。

**正常完成场景结论：通过。**

### 3.2 真实 Skill 路由与问题场景

测试会话：`f83f3705-8a91-4b44-986b-7a8edb631e34`
用户请求：包含“虚拟人鉴权失败”的排障请求。

Claude 实际调用顺序：

```text
avatar-workflow-entry
  -> avatar-troubleshoot
  -> references/authentication-failed.md
```

实际结果：

- SQLite 自动记录并上传。
- workflow 正确归类为 `troubleshoot`。
- `avatar-workflow-entry` 和 `avatar-troubleshoot` 各生成一条 invocation。
- 同目录、接续窗口内复用原 workflow_id。
- 没有错误创建第二条“中断 + 完成”的拆分 workflow。

**问题场景结论：通过。** 问题请求不会导致 telemetry 丢失，也不会被误报为 completed。

### 3.3 真实 HTTP 异常场景

以下为真实运行后端上的请求级验证：版本错误、anonymousId 错误、revision 非法均被拒绝且不写库；合法与非法记录混合时只落合法数据；超过 500 条时超限记录被明确返回且不污染数据库。

**真实接口异常场景结论：通过。**

### 3.4 真实场景残余限制

本地直接访问以下接口均能得到 HTTP 200，尚未证明生产环境已配置认证和限流：

- `POST /zs_admin/avatarTelemetry/report`
- `GET /zs_admin/avatarTelemetry/workflowStat`
- `GET /zs_admin/avatarTelemetry/skillUsage`

这属于部署安全验证项，不是本地数据正确性失败。

## 四、代码完整性测试

### 4.1 客户端源码完整性

客户端全量命令：

```text
python -m pytest -q
```

结果：`174 passed, 1 warning in 8.39s`。

覆盖 `tracker.py`、`telemetry_common.py`、`db_schema.py`、`uploader.py`、`completion_check.py`、`web_delivery.py` 及当前 Skill 路由和鉴权失败 reference。

### 4.2 后端源码完整性

后端 telemetry 定向测试：`Tests run: 11, Failures: 0, Errors: 0, Skipped: 0`，`BUILD SUCCESS`。

覆盖隐私拒绝、状态校验、anonymous ID、revision、单条数据库异常、批次上限、cancelled 和 first_prompt。

### 4.3 构建产物完整性

测试发现旧 `target/appassembler` 包仍使用 `PRIVACY_NOTICE_VERSION=2.0`，而当前源码和客户端契约为 `2.1`。重新构建并使用新包后，HTTP 契约全部通过。

```text
mvn "-pl" "zhisheng-interact-admin" "-am" "-Dmaven.test.skip=true" package
```

该问题属于构建产物漂移，不是当前 telemetry 源码逻辑错误。发布必须从当前源码重新打包。

### 4.4 完整模块回归状态

完整 admin Maven 测试仍有两个既有的、与 telemetry 无关的初始化错误：

```text
NoticeTest.initializationError
AvatarInteractiveRecordNewServiceImplTest.initializationError
```

telemetry 定向测试通过，跳过测试打包成功；两个历史错误需要修复或正式豁免。

### 4.5 本章结论

telemetry 相关客户端和后端代码具备完整测试覆盖，源码可构建，真实运行包已验证。当前完整 admin 模块并非全绿，阻塞点来自两个无关历史测试以及旧运行包漂移。

## 五、昨日历史测试结果

### 5.1 昨日真实本地闭环

测试会话：`local-e2e-02c552ffd4d1`

- tracker 收集 prompt、PreToolUse/Skill、SessionEnd。
- SQLite 生成 workflow 和 invocation。
- uploader 上传到本地后端并写入 MySQL。
- workflow：1 条，`uploaded=1`，`dead_letter=0`。
- invocation：2 条，均 `uploaded=1`。
- uploader 第二实例无法获得锁，原实例正常排空队列。
- 同一 revision 重放后仍无重复数据。

### 5.2 昨日结果结论

昨日真实 Claude 会话已纳入本次 MySQL 对账和重复数据检查，结果与今天的自动化测试结论一致：上报闭环和幂等行为符合预期。

## 六、已运行真实完整场景

本节只列真实 Claude Code 会话或真实运行工程，不把纯单元测试当作真实场景，也不把外部环境故障算作产品失败。

### 6.1 成功完成的真实场景

| 场景 | 实际运行内容 | 结果/完成证据 |
|---|---|---|
| Web 健身教练 quick (`wf_62297d56...`) | Web SDK 工程、文本问答、短语音问答、真实鉴权、真实首帧和运行验证 | `completed`，`verification_flag`；文本和语音均通过，`errors=[]` |
| Web 展厅 strict (`wf_06f231db...`) | strict 设计/计划/实现、文本驱动、透明背景、字幕、队列、停止、真实首帧 | `completed`，`verification_flag`；最终 gate `ready_to_deliver=true` |
| 语音/全双工能力 (`wf_94911a76...`) | 真实路由到 `voice-interact`、`full-duplex`，完成验证收口 | `completed`，`verification_flag` |
| 字幕/配置扩展 (`wf_ec6dc048...`) | 字幕配置、透明/渲染相关配置、凭据和产物检查 | `completed`，`verification_flag` |

### 6.2 成功场景的 workflow 明细

以下字段直接来自本地 SQLite `workflows` 表；`uploaded=1` 表示该最终 revision 已收到后端 ACK，`dead_letter=0` 表示未进入死信。

| 场景 | workflow_id | workflow_type | status | completion_method | revision | uploaded | dead_letter |
|---|---|---|---|---|---:|---:|---:|
| Web 健身教练 quick | `wf_62297d56-beeb-4e49-9ffb-c4a15a839b8b` | `sdk_integration` | `completed` | `verification_flag` | 5 | 1 | 0 |
| Web 展厅 strict | `wf_06f231db-60d0-4b98-b604-02a538ce64f0` | `sdk_integration` | `completed` | `verification_flag` | 6 | 1 | 0 |
| 语音/全双工 | `wf_94911a76-deac-4953-a0c8-bf2db6c0f4aa_bbe23ef3` | `sdk_integration` | `completed` | `verification_flag` | 11 | 1 | 0 |
| 字幕/配置扩展 | `wf_ec6dc048-e726-4c45-bfcc-c2afc0dd0458_3a523789` | `sdk_integration` | `completed` | `verification_flag` | 16 | 1 | 0 |

四条成功 workflow 的 `completion_detail` 均为：

```json
{"issues_found": 0, "issues_fixed": 0}
```

### 6.3 成功场景的 invocation 明细

#### Web 健身教练 quick

所属 workflow：`wf_62297d56-beeb-4e49-9ffb-c4a15a839b8b`

| invocation_id | skill_name | source | hit_count | revision | uploaded | dead_letter |
|---|---|---|---:|---:|---:|---:|
| `inv_3588ecddf29440e6` | `avatar-workflow-entry` | `slash` | 1 | 1 | 1 | 0 |
| `inv_d8207908c048408d` | `avatar-brainstorming` | `read` | 1 | 1 | 1 | 0 |
| `inv_6360199559ca479a` | `avatar-executing` | `read` | 1 | 1 | 1 | 0 |
| `inv_4b2734503e6f40ac` | `avatar-credentials` | `read` | 1 | 1 | 1 | 0 |
| `inv_45c1cbb633af470e` | `avatar-artifact-download` | `read` | 1 | 1 | 1 | 0 |
| `inv_df89c223bea440eb` | `avatar-network-debug` | `read` | 1 | 1 | 1 | 0 |

#### Web 展厅 strict

所属 workflow：`wf_06f231db-60d0-4b98-b604-02a538ce64f0`

| invocation_id | skill_name | source | hit_count | revision | uploaded | dead_letter |
|---|---|---|---:|---:|---:|---:|
| `inv_4094e24861794d16` | `avatar-workflow-entry` | `slash` | 1 | 1 | 1 | 0 |
| `inv_221a8bee7e604ac5` | `avatar-brainstorming` | `read` | 1 | 1 | 1 | 0 |
| `inv_67af88efd02c46ff` | `avatar-executing` | `read` | 1 | 1 | 1 | 0 |
| `inv_fb76c782595e41fa` | `avatar-planning` | `read` | 1 | 1 | 1 | 0 |
| `inv_b6d718adceb144ec` | `subtitle-setup` | `read` | 1 | 1 | 1 | 0 |
| `inv_11d997b70bad4f97` | `transparent-bg` | `read` | 1 | 1 | 1 | 0 |
| `inv_3d5dceb269604627` | `text-driver` | `read` | 1 | 1 | 1 | 0 |
| `inv_7acdc745d494490f` | `avatar-preflight` | `read` | 1 | 1 | 1 | 0 |

#### 语音/全双工

所属 workflow：`wf_94911a76-deac-4953-a0c8-bf2db6c0f4aa_bbe23ef3`

| invocation_id | skill_name | source | hit_count | revision | uploaded | dead_letter |
|---|---|---|---:|---:|---:|---:|
| `inv_65e45dd9554b49af` | `avatar-executing` | `read` | 1 | 1 | 1 | 0 |
| `inv_e8e7848030414e2c` | `avatar-workflow-entry` | `slash` | 1 | 1 | 1 | 0 |
| `inv_451843c5b7884378` | `voice-interact` | `read` | 1 | 1 | 1 | 0 |
| `inv_0c173bf530b54761` | `full-duplex` | `read` | 1 | 1 | 1 | 0 |

#### 字幕/配置扩展

所属 workflow：`wf_ec6dc048-e726-4c45-bfcc-c2afc0dd0458_3a523789`

| invocation_id | skill_name | source | hit_count | revision | uploaded | dead_letter |
|---|---|---|---:|---:|---:|---:|
| `inv_2967cf22f0dc4277` | `avatar-executing` | `read` | 1 | 1 | 1 | 0 |
| `inv_95e9ad1b97c14349` | `subtitle-render` | `read` | 1 | 1 | 1 | 0 |
| `inv_7de03e04340e4478` | `avatar-config-authoring` | `read` | 1 | 1 | 1 | 0 |
| `inv_646a10a118934eb0` | `subtitle` | `read` | 1 | 1 | 1 | 0 |
| `inv_47cc7586015f4922` | `avatar-workflow-entry` | `read` | 1 | 1 | 1 | 0 |
| `inv_74e930d461ce46b6` | `avatar-subtitle` | `read` | 1 | 1 | 1 | 0 |
| `inv_c4522c35c5054b57` | `subtitle-setup` | `read` | 1 | 1 | 1 | 0 |
| `inv_d250ac88ab0e4950` | `avatar-artifact-download` | `read` | 1 | 1 | 1 | 0 |
| `inv_23b10a7ccb594148` | `avatar-credentials` | `read` | 1 | 1 | 1 | 0 |

### 6.4 昨日真实闭环的 workflow/invocation 明细

#### `local-e2e-02c552ffd4d1`

| workflow_id | workflow_type | status | revision | uploaded | dead_letter |
|---|---|---|---:|---:|---:|
| `wf_local-e2e-02c552ffd4d1` | `troubleshoot` | `interrupted` | 4 | 1 | 0 |

| invocation_id | skill_name | source | hit_count | revision | uploaded | dead_letter |
|---|---|---|---:|---:|---:|---:|
| `inv_e6f1ae8e18af4f96` | `avatar-workflow-entry` | `skill_tool` | 1 | 1 | 1 | 0 |
| `inv_667335f3c1514275` | `avatar-troubleshoot` | `skill_tool` | 1 | 1 | 1 | 0 |

该会话的 workflow 虽然最终业务状态是 `interrupted`，但上报闭环完整：workflow 和 invocation 均已 ACK，重放没有重复落库。

#### 外部环境问题会话记录

这些记录不是 telemetry 代码失败，而是运行环境或项目状态未满足交付条件；它们保留为非终态，不能伪造为 completed。

| 场景 | workflow_id | status | revision | invocation 列表 |
|---|---|---|---:|---|
| Android wrapper 损坏 | `wf_362289a1-68aa-43be-b6b0-7535105acd35` | `interrupted` | 5 | `avatar-workflow-entry` (`inv_107b7b5ae7fe4bdc`), `avatar-executing` (`inv_e578bccb106f481f`) |
| telemetry smoke 缺运行证据 | `wf_00e67b7e-24ad-4213-a4a1-9961cddd0285` | `interrupted` | 11 | `avatar-workflow-entry` (`inv_89850cfacde247c9`), `avatar-brainstorming` (`inv_ffdc0aa4937e4e72`) |
| 第二次鉴权失败排障 | `wf_8b52e875-9c3f-47fa-9d03-3f5b7aa5d2aa` | `interrupted` | 6 | `avatar-workflow-entry` (`inv_a00a10facbad4d2a`), `avatar-troubleshoot` (`inv_93201ed3d50847aa`) |

### 6.5 问题修复与 workflow/invocation 对照

下面四个问题都能追溯到具体的 telemetry 记录。Web 三个问题发生在会话中间，修复后继续更新同一个 workflow，最终以 `completed` 收口；不是把已经结束的失败记录改写成成功。

| 问题 | workflow | 相关 invocation | 修复后的最终状态 |
|---|---|---|---|
| 技能库模板 `gradle-wrapper.jar` 损坏 | `wf_362289a1-68aa-43be-b6b0-7535105acd35` | `inv_107b7b5ae7fe4bdc` `avatar-workflow-entry`；`inv_e578bccb106f481f` `avatar-executing` | 原始 workflow 保持 `interrupted`；wrapper 后续已修复，工程重新执行 `gradlew --version` 和 `assembleDebug` 成功，但尚未重新创建 Android 完整验证 workflow |
| Web `[11200] avatar authentication failed` | `wf_62297d56-beeb-4e49-9ffb-c4a15a839b8b` | `inv_3588ecddf29440e6` `avatar-workflow-entry`；`inv_d8207908c048408d` `avatar-brainstorming`；`inv_6360199559ca479a` `avatar-executing`；`inv_4b2734503e6f40ac` `avatar-credentials`；`inv_45c1cbb633af470e` `avatar-artifact-download`；`inv_df89c223bea440eb` `avatar-network-debug` | 同一 workflow 最终 `completed`，`completion_method=verification_flag`，`revision=5` |
| Web 首帧失败 | `wf_06f231db-60d0-4b98-b604-02a538ce64f0`；另在 quick 验证中复现于 `wf_62297d56-beeb-4e49-9ffb-c4a15a839b8b` | strict：`inv_4094e24861794d16` `avatar-workflow-entry`；`inv_221a8bee7e604ac5` `avatar-brainstorming`；`inv_67af88efd02c46ff` `avatar-executing`；`inv_fb76c782595e41fa` `avatar-planning`；`inv_b6d718adceb144ec` `subtitle-setup`；`inv_11d997b70bad4f97` `transparent-bg`；`inv_3d5dceb269604627` `text-driver`；`inv_7acdc745d494490f` `avatar-preflight`。quick 记录见上一行 workflow 的 invocation 列表 | strict 最终 `completed`，`first_frame=true`；quick 最终也为 `completed` |
| Web `config_mismatch` | `wf_62297d56-beeb-4e49-9ffb-c4a15a839b8b` | 与 Web quick 同一组 invocation：`avatar-workflow-entry`、`avatar-brainstorming`、`avatar-executing`、`avatar-credentials`、`avatar-artifact-download`、`avatar-network-debug` | 清理旧项目 Node 进程并重启后，同一 workflow 最终 `completed`，`revision=5` |

### 6.6 真实运行但未完成的场景及问题

| 场景 | 实际问题 | telemetry 结果 |
|---|---|---|
| Android 健身教练 quick（原始会话） | 原始运行时技能库模板 `gradle-wrapper.jar` 损坏，Gradle 无法启动；未伪造构建、首帧或录音结论 | 原始 workflow 为 `interrupted`；该外部模板问题随后已修复 |
| telemetry smoke | 浏览器运行证据缺少 `connected/stream_start/first_frame/text`，后续由补偿收口标记中断 | `interrupted`，`awaiting_runtime_verification` |
| Web 鉴权失败排障 | 真实场景曾出现 `[11200] avatar authentication failed`；最终定位为 app/scene 不匹配及场景未发布，修正并重新验证 | 原问题会话中断；后续 Web quick/strict 完成 |
| Web strict 首帧 | Playwright Chromium 缺少 H.264，导致 `first_frame` 不触发 | 非业务代码失败；切换系统 Edge CDP 后通过 |
| Web quick 服务状态 | 旧 Node 进程持有旧 appId，触发 `config_mismatch` | 清理本项目状态文件记录的进程后恢复 |

### 6.7 昨日真实本地上报会话

| 会话 | 场景 | 实际结果 |
|---|---|---|
| `local-e2e-02c552ffd4d1` | 入口路由、排障 Skill、SessionEnd、SQLite、uploader、HTTP、MySQL | workflow 1 条、invocation 2 条，全部上传；重放无重复 |
| `8b52e875-9c3f-47fa-9d03-3f5b7aa5d2aa` | 第二次真实鉴权失败路由 | SQLite 自动记录并上传，workflow 类型 `troubleshoot` |

### 6.8 真实完整场景结论

已完成的真实终态场景共 4 条：Web quick、Web strict、语音/全双工、字幕/配置扩展。Web quick 和 Web strict 中的鉴权失败、首帧失败、服务状态问题在修复后均进入了对应最终 workflow 的 `completed` 终态，完成证据为 `verification_flag`、`issues_found=0`、`issues_fixed=0`。原始失败会话保留为历史记录，不被篡改。Android 原始 workflow 仍是 `interrupted`，因为 wrapper 修复发生在该会话结束之后，尚未重新跑 Android 的完整验证收口。

这里的状态规则是：**中间步骤失败不立即终结 workflow**。只要当前会话仍在运行，AI 修复问题后可以继续写入新的 revision；最终验证通过并执行 SessionEnd 时，同一个 workflow 才会被更新为 `completed`。Web strict 的首帧失败就是这个路径：首次浏览器验证失败，切换支持 H.264 的 Edge CDP 后重新验证通过，最终同一个 `wf_06f231db...` 以 `completed` 收口。只有 workflow 已经被 SessionEnd 标记为 `interrupted`/`cancelled`，后续才会保留原记录，并通过接续条件创建或复用后续 workflow。

### 6.9 外部环境问题的修复状态

| 问题 | 修复状态 | 修复后结果 |
|---|---|---|
| 技能库模板 `gradle-wrapper.jar` 损坏 | 已修复；当前 JAR 可读取且含 `GradleWrapperMain` | Android 工程 `gradlew --version` 正常，`assembleDebug` 已 `BUILD SUCCESSFUL` |
| Web `[11200] avatar authentication failed` | 已修复 app/scene 配对并发布场景 | Web quick 最终 workflow `completed` |
| Web 首帧失败 | 已确认是 Chromium 缺 H.264，改用 Edge CDP 验证 | Web strict/quick 最终 workflow `completed`，`first_frame=true` |
| Web `config_mismatch` | 已清理持有旧凭据的项目 Node 进程并重启 | Web quick 最终 workflow `completed` |

### 6.10 本地真实 workflow 总账

截至本报告生成时，SQLite 中共有 31 条真实 workflow：

| 状态 | 数量 | 说明 |
|---|---:|---|
| `completed` | 4 | 上述 4 条真实终态场景，均有 `verification_flag` |
| `interrupted` | 15 | 包括 Android 构建阻塞、telemetry smoke、鉴权排障和用户中断 |
| `cancelled` | 12 | 用户取消或在确认/凭据门禁阶段主动结束 |
| 合计 | 31 | 当前数据库分组统计 |

数据库按 `status` 分组的实际结果为 `completed=4`、`interrupted=15`、`cancelled=12`，合计 31 条。没有把临时 `report-e2e-*` HTTP 数据算入这份真实会话总账。

## 七、Agent 运行影响测试

### 7.1 执行方式

- `tracker.py` 只在 Hook 中完成本地 SQLite 事务，提交后再异步启动 uploader。
- uploader 使用独立子进程和文件锁，不占用 Agent 当前执行进程。
- 网络请求失败、服务端拒绝和退避都在 uploader 内处理，不向 Agent 主流程同步等待重试。
- ACK 只更新本地 `uploaded` 状态，不回写或阻塞当前 Skill 的执行结果。

### 7.2 实测结论

| 场景 | 对 Agent 的影响 | 结果 |
|---|---|---|
| 正常 Hook 上报 | Agent 继续执行后续 Skill/工具 | 通过 |
| uploader 并发 | 第二实例退出，不阻塞主流程 | 通过 |
| 网络失败 | 数据保留待重试，Agent 不被卡住 | 通过 |
| 永久拒绝 | 进入 dead letter，Agent 不重复等待 | 通过 |
| SQLite 损坏 | 自动重建本地库，当前请求继续 | 通过 |
| consent 撤回 | 停止上传，但业务 Skill 继续 | 通过 |

### 7.3 本章结论

统计和上报逻辑不会影响 Agent 主流程。它的设计目标是“本地快速记录、后台异步上传、失败不阻塞业务”；当前测试结果符合这一目标。

## 八、总体结论与上线前事项

### 8.1 本地测试结论

从 telemetry 功能本身看：**通过**。已验证正常完成、Skill 路由、会话中断、接续、网络失败、服务端拒绝、批量上限、重复上报、进程异常、SQLite 损坏和 MySQL 落库一致性。

### 8.2 上线前必须完成

1. 将 `config/telemetry.json` 的 endpoint 换成正式 HTTPS 地址。
2. 将 `config/privacy_notice.json` 中的主体、存储地区、联系方式、删除流程替换为正式内容。
3. 确认生产网关对上报和统计接口提供认证、限流及来源控制。
4. 处理或正式豁免两个非 telemetry Maven 测试初始化错误。
5. 在干净目录重新安装 Claude plugin，并执行一次安装后冒烟测试。

### 8.3 发布判定

**本地验证：通过。**
**直接发布生产：暂不建议，需先完成 8.2 的配置、安全和发布流程收口。**
