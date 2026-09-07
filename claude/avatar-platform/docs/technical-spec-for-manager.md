# 虚拟人插件使用统计技术方案

> 历史方案：本文记录 2026-08-24 前的 SQLite 设计，已被 `state.json + 异步 Webhook` 当前实现替代。当前设计以 [telemetry-architecture-and-validation.md](telemetry-architecture-and-validation.md) 为准。

**目标读者**：技术管理层  
**文档版本**：1.0  
**日期**：2026-08-04

---

## 一、业务目标

通过埋点统计，回答三个核心问题：

1. **每个功能（skill）的使用次数** — 用户最常用哪些功能
2. **任务完成率** — 用户能否顺利跑完流程
3. **用户规模** — 有多少设备/账号在使用

**价值**：
- 发现高频使用和冷门功能，指导迭代优先级
- 定位卡点和故障场景，优化用户体验
- 评估插件推广效果，支撑运营决策

---

## 二、架构概览

```
┌─────────────────────────────────────────────────────────┐
│ 客户端（用户本地）                                       │
│ ┌─────────────┐                                         │
│ │ Claude Code │ 会话进行中                              │
│ │   插件      │ ↓                                       │
│ └─────────────┘ hook 触发（每轮对话、每次工具调用）    │
│        ↓                                                 │
│ ┌─────────────────────────────────────────────────┐    │
│ │ tracker.py（埋点模块）                          │    │
│ │ • 判定业务意图（是否虚拟人相关）                │    │
│ │ • 记录 skill 调用（哪个功能被用了）             │    │
│ │ • 扫盘产物（APK/dist/验证结果）                 │    │
│ │ • 判定完成状态（completed/interrupted/failed）  │    │
│ └─────────────────────────────────────────────────┘    │
│        ↓ 实时落库                                       │
│ ┌─────────────────────────────────────────────────┐    │
│ │ SQLite（本地数据库）                            │    │
│ │ • workflows 表（工作流）                        │    │
│ │ • invocations 表（skill 调用记录）              │    │
│ │ • uploaded=0 标记未上传                         │    │
│ └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
        ↓ 批量上传（手动/定时）
┌─────────────────────────────────────────────────────────┐
│ uploader.py（上传器）                                   │
│ • 读取 uploaded=0 的记录（批量 50 条）                  │
│ • POST /zs_admin/avatarTelemetry/report                │
│ • 只标记被服务端确认的为 uploaded=1                     │
│ • 未确认的留待下次重试（容错）                          │
└─────────────────────────────────────────────────────────┘
        ↓ HTTP
┌─────────────────────────────────────────────────────────┐
│ 服务端（zhisheng-interact-admin）                       │
│ ┌─────────────────────────────────────────────────┐    │
│ │ AvatarTelemetryController                       │    │
│ │ • POST /report — 接收上报                       │    │
│ │ • GET /skillUsage — skill 使用统计              │    │
│ │ • GET /workflowStat — 完成率统计                │    │
│ │ • GET /userStat — 用户规模                      │    │
│ │ • GET /accessPathPreference — 接入路径偏好      │    │
│ │ • GET /faultSceneStat — 高频故障场景            │    │
│ │ • GET /skillCompletionStat — skill 卡点分析     │    │
│ │ • GET /diagnosisReport — 诊断总览               │    │
│ └─────────────────────────────────────────────────┘    │
│        ↓                                                 │
│ ┌─────────────────────────────────────────────────┐    │
│ │ AvatarTelemetryServiceImpl                      │    │
│ │ • 校验（必填项、枚举值、时间格式）              │    │
│ │ • 幂等去重（workflow_id / workflow_id+skill_name）│  │
│ │ • 容错（单条失败不影响整批）                    │    │
│ └─────────────────────────────────────────────────┘    │
│        ↓                                                 │
│ ┌─────────────────────────────────────────────────┐    │
│ │ MySQL / DM8                                     │    │
│ │ • avatar_telemetry_workflow（工作流表）        │    │
│ │ • avatar_telemetry_invocation（调用记录表）    │    │
│ └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**关键设计**：
- **边进行边记录** — 不等会话结束，实时落本地库
- **三层幂等** — 客户端本地、上传确认、服务端去重，保证统计不重复
- **容错优先** — 单条失败不影响整批，网络异常保留数据重试


## 三、客户端详细流程

### 3.1 核心数据结构

#### workflows 表（工作流）

一个工作流 = 一次完整的用户任务。首次由 Claude 会话创建；短时断线、`/resume` 或插件重载
导致 session 变化时，满足接续条件的任务仍使用原 workflow ID。

| 字段 | 含义 | 何时写入 | 何时更新 |
|---|---|---|---|
| workflow_id | 工作流 ID | 第一次 prompt | 不变 |
| anonymous_id | 匿名设备 ID | 第一次 prompt | 不变 |
| started_at | 开始时间 | 第一次 prompt | 不变 |
| ended_at | 结束时间 | SessionEnd / 补偿收口 | SessionEnd / 补偿收口 |
| status | 状态 | 第一次 prompt（in_progress） | SessionEnd / Reporter / 补偿收口 |
| workflow_type | 类型 | 首次 skill 调用 | 不变（首次覆盖） |
| completion_method | 完成判据 | 机会性扫盘 / SessionEnd | SessionEnd 覆盖 |
| completion_confidence | 置信度 | 机会性扫盘 / SessionEnd | SessionEnd 覆盖 |

#### invocations 表（skill 调用记录）

一条记录 = 一个 skill 在一个工作流内的使用情况

| 字段 | 含义 | 何时写入 | 何时更新 |
|---|---|---|---|
| invocation_id | 调用 ID | 首次检测到 skill | 不变 |
| workflow_id | 所属工作流 | 首次检测到 skill | 不变 |
| skill_name | skill 名称 | 首次检测到 skill | 不变 |
| source | 来源 | 首次检测到 skill | 不变 |
| hit_count | 命中次数 | 首次（1） | 每次命中 +1 |
| first_at | 首次命中时间 | 首次检测到 skill | 不变 |
| last_at | 末次命中时间 | 首次检测到 skill | 每次命中更新 |


### 3.2 完整生命周期（时间线）

**T0: 用户输入提示词**
```
用户输入: /avatar-platform:avatar-verification 做 Android SDK
触发: PromptResponse hook
```

操作：
1. 提取 session_id（Claude Code 生成的 UUID）
2. 判定业务意图：检测到斜杠命令 → has_avatar_signal=1
3. 建 workflow 行：
   ```sql
   INSERT INTO workflows (
     workflow_id, anonymous_id, started_at,
     status, has_avatar_signal
   ) VALUES (
     'wf_abc...', 'anon_xxx', '2026-08-04T10:00:00Z',
     'in_progress', 1
   )
   ```

**T1: 模型调用 Skill 工具**
```
模型操作: Skill('avatar-platform:avatar-verification')
触发: PreToolUse hook
```

操作：
1. 推断 workflow_type：
   ```sql
   UPDATE workflows
   SET workflow_type = 'sdk_integration'
   WHERE workflow_id = 'wf_abc...'
   ```

2. 记录 skill 调用：
   - 查询 (workflow_id, skill_name) 是否存在
   - 不存在 → INSERT
   - 已存在 → UPDATE hit_count+1, last_at

**T2: 模型 Write 文件**
```
模型操作: Write('<project-root>/app/build.gradle')
触发: PreToolUse hook
```

操作：
1. 判定路径是否在插件目录外
2. 是 → 更新 has_real_side_effect=1

**T3: 下一轮 prompt（机会性扫盘）**
```
用户输入: 继续构建
触发: PromptResponse hook
```

操作：
1. 检查已有 completion_method
   - 若已有硬证据 → 跳过扫盘
   - 否则 → 扫盘（APK/dist/verification_results）
2. 假设找到 APK：
   - 验证 ZIP 格式、检查必需文件、验证 mtime
   - 通过 → method='artifact', confidence='high'
3. 更新 workflow（不改 status）：
   ```sql
   UPDATE workflows
   SET completion_method = 'artifact',
       completion_confidence = 'high',
       completion_detail = '{"apk":"...", "size":12345}'
   WHERE workflow_id = 'wf_abc...'
   ```
   注意：status 保持 'in_progress'（产物在中途出现，但会话还在继续）

**T4: 会话结束**
```
用户操作: 关闭终端 / Ctrl+C
触发: SessionEnd hook（如果触发）
```

操作：
1. 读取当前状态：status='in_progress', method='artifact'
2. 决策最终状态：
   - 有硬产物 → final='completed'
   - 无产物 → final='interrupted'
3. 更新 workflow：
   ```sql
   UPDATE workflows
   SET status = 'completed', ended_at = '2026-08-04T10:30:00Z'
   WHERE workflow_id = 'wf_abc...'
   ```

**T4备选: SessionEnd 不触发（硬退出）**
- 记录保持 status='in_progress'
- 等待补偿收口（见 T5）

**T5: 30 分钟后补偿收口**
```
用户操作: 开新会话
触发: PromptResponse hook（下次会话第一次）
```

操作：
1. 查询遗留工作流：
   ```sql
   SELECT workflow_id, completion_method
   FROM workflows
   WHERE status = 'in_progress'
     AND workflow_id != 'wf_new...'
     AND started_at < (now - 30分钟)
   ```
2. 判定最终状态（不再扫盘）：
   - method in ('artifact', 'verification_flag') → 'completed'
   - 否则 → 'interrupted'
3. 更新遗留工作流

**T6: 上传**
```
操作: python uploader.py
```

操作：
1. 退避检查（连续失败 → 指数退避）
2. 读取 uploaded=0 的记录（批量 50 条）
3. 构造 JSON payload
4. POST /zs_admin/avatarTelemetry/report
5. 解析 acceptedWorkflowIds / acceptedInvocationIds
6. 只标记被确认的为 uploaded=1

### 3.3 关键时机总结

| 时机 | 触发者 | workflow 更新 | invocation 更新 |
|---|---|---|---|
| 首次 prompt | PromptResponse | INSERT（建行） | - |
| 首次 skill 调用 | PreToolUse | UPDATE workflow_type | INSERT（建行） |
| 重复 skill 调用 | PreToolUse | - | UPDATE hit_count+1 |
| Write 插件外文件 | PreToolUse | UPDATE has_real_side_effect | - |
| 中途 prompt | PromptResponse | UPDATE completion_* | - |
| SessionEnd | SessionEnd hook | UPDATE status, ended_at | - |
| 30 分钟后 | PromptResponse（新会话） | UPDATE status, ended_at（遗留） | - |
| 上传成功 | uploader.py | UPDATE uploaded=1 | UPDATE uploaded=1 |


## 四、服务端详细流程

### 4.1 上报接口（POST /report）

**处理步骤：**

1. **Controller 接收请求**
2. **Service 逐条处理**（单条失败不影响整批）
3. **工作流幂等处理**
   - 按 workflow_id 查询是否存在
   - 不存在 → INSERT
   - 已存在 → UPDATE（已终结状态不被 in_progress 回退）
4. **调用记录幂等处理**
   - 按 (workflow_id, skill_name) 查询是否存在
   - 不存在 → INSERT
   - 已存在 → UPDATE（hitCount 取较大值，不累加）
5. **返回确认列表**
   - acceptedWorkflowIds / acceptedInvocationIds
   - rejected（校验失败的记录）

**幂等关键点：**

| 表 | 幂等键 | 原因 |
|---|---|---|
| workflow | workflow_id | 客户端生成，同一会话唯一 |
| invocation | (workflow_id, skill_name) | invocation_id 会因本地库重建而变化 |

**hitCount 为什么取较大值而非累加？**

客户端上报的已经是累计值：
```
首次上报: hitCount=3（本地已累加）
重传:     hitCount=3（同样的累计值）
```
如果服务端累加 → 3 + 3 = 6（错误）
取较大值 → max(3, 3) = 3（正确）

### 4.2 统计接口（7 个）

#### 基础统计（3 个）

| 接口 | 用途 | 核心 SQL |
|---|---|---|
| GET /skillUsage | skill 使用次数 | COUNT(DISTINCT workflow_id), SUM(hit_count) |
| GET /workflowStat | 完成率 | COUNT(*) GROUP BY status, confidence |
| GET /userStat | 用户规模 | COUNT(DISTINCT anonymous_id) |

#### 运营分析（4 个 - 新增）

| 接口 | 用途 | 关键逻辑 |
|---|---|---|
| GET /accessPathPreference | 接入路径偏好 | 按 workflow_type 分类，各自完成率 |
| GET /faultSceneStat | 高频故障场景 | 从 completion_detail 关键词识别故障类型 |
| GET /skillCompletionStat | skill 卡点分析 | 找非完成工作流中"最后一个 skill" |
| GET /diagnosisReport | 诊断总览 | 聚合以上 4 个接口 |

**故障场景分类（示例）**

从 completion_detail 识别关键词：
- 含 "credential/apikey/鉴权" → credential_auth
- 含 "websocket/timeout/网络" → network_connection
- 含 "gradle/dependency/构建" → sdk_build_dependency
- 含 "docqa/知识库" → knowledge_base
- 含 "sceneid/形象/资源" → resource_config
- 含 "microphone/录音/权限" → voice_permission

**统计口径（噪声过滤）**

所有统计接口只查满足条件的工作流：
```sql
WHERE has_avatar_signal = 1 AND has_real_side_effect = 1
```

过滤掉：
- 纯浏览（只 Read skill.md）
- 开发插件本身（Write 插件目录内文件）

实测砍掉 54% 噪声数据。


## 五、关键设计决策

### 5.1 三层幂等保证

**为什么需要三层？**

| 层级 | 场景 | 解决的问题 |
|---|---|---|
| **客户端本地幂等** | 同一会话 hook 触发几十次 | 避免本地数据库重复记录 |
| **上传确认幂等** | 网络超时、部分接收 | 只清理被确认的，未确认的留待重试 |
| **服务端幂等** | 客户端重传、本地库重建 | 避免服务端数据库重复计数 |

**实现细节：**

1. **客户端本地**
   - workflow 主键：workflow_id
   - invocation 唯一键：(workflow_id, skill_name)
   - 写入策略：REPLACE INTO / ON CONFLICT UPDATE

2. **上传确认**
   ```python
   # 服务端返回
   acceptedWorkflowIds = ["wf_abc", "wf_def"]
   acceptedInvocationIds = ["inv_xyz"]
   
   # 客户端只清理被确认的
   UPDATE workflows SET uploaded=1 
   WHERE workflow_id IN (acceptedWorkflowIds)
   ```

3. **服务端**
   - workflow 查询：getById(workflow_id)
   - invocation 查询：WHERE workflow_id=? AND skill_name=?
   - hitCount 取较大值而非累加

### 5.2 五重触发上传机制

**为什么需要多重触发？**

| 问题 | 单一触发的风险 | 多重触发的解决 |
|---|---|---|
| SessionEnd 不可靠 | 硬退出丢数据 | 补偿收口 + 定时任务 |
| 数据延迟高 | 长会话数据积压几小时 | 关键节点实时上传 |
| 网络抖动 | 一次失败整批丢失 | 多次重试机会 |

**五重触发时机：**

1. **avatar-workflow-entry 触发（入口点）**
   ```python
   # 用户开始新任务
   if skill == 'avatar-workflow-entry':
       trigger_upload_if_needed(conn)  # 清空历史积压
   ```
   - 频率：每次新任务开始
   - 目的：确保新任务开始时，历史数据已上传

2. **平台工具调用后（顺手上传）**
   ```python
   # 配置凭据、发布资源等关键操作后
   if PLATFORM_TOOL_RE.search(cmd):  # xfyun_*.py
       trigger_upload_if_needed(conn)
   ```
   - 频率：每次配置/发布操作
   - 目的：关键节点实时上传，减少延迟

3. **SessionEnd 时（主要路径）**
   ```python
   # 会话正常结束
   subprocess.Popen([sys.executable, 'uploader.py'])
   ```
   - 频率：每次会话结束
   - 覆盖率：~80%
   - 目的：正常流程上传

4. **补偿收口后（容错机制）**
   ```python
   # 30 分钟前遗留的 in_progress 工作流
   if stale:
       trigger_upload_if_needed(conn)
   ```
   - 频率：SessionEnd 未触发时
   - 覆盖率：~15%
   - 目的：容错，避免数据丢失

5. **定时任务（兜底）**
   ```bash
   # cron / Task Scheduler
   0 * * * * python uploader.py
   ```
   - 频率：每小时
   - 覆盖率：~5%
   - 目的：最终兜底

**智能节流：**
```python
def trigger_upload_if_needed(conn):
    # 只有积压 >= 10 条才触发
    count = conn.execute(
        'SELECT COUNT(*) FROM workflows WHERE uploaded = 0'
    ).fetchone()[0]
    
    if count >= 10:
        subprocess.Popen(['uploader.py'])
```

避免频繁触发，减少网络开销。

### 5.3 完成判定分级

**为什么需要 method + confidence？**

| 判据 | 可信度 | 示例 | 能否伪造 |
|---|---|---|---|
| artifact | high | APK ZIP 校验通过 | ✗ 模型无法伪造 |
| verification_flag | high | 7 层验证通过 | ✗ 外部工具验证 |
| artifacts_file | medium | 平台侧交付物 ID | △ 有 ID 但未验证可用性 |

**统计给两个完成率：**
- completedWide = 所有 status=completed 的（含自报）
- completedHard = 只算 completion_confidence=high 的（硬证据）

差距反映自报数据占比。

### 5.4 补偿收口机制

**触发时机：** 下次会话启动时（PromptResponse hook 第一次）

**处理逻辑：**
```python
# 查询 30 分钟前遗留的 in_progress
SELECT workflow_id, completion_method
FROM workflows
WHERE status = 'in_progress'
  AND workflow_id != 'wf_current'
  AND started_at < (now - 30分钟)

# 判定最终状态（不再扫盘）
if method in ('artifact', 'verification_flag', 'artifacts_file'):
    final = 'completed'
else:
    final = 'interrupted'

# 更新
UPDATE workflows SET status=?, ended_at=? WHERE workflow_id=?
```

**为什么不再扫盘？**

30 分钟后用户目录可能已经清理，扫盘不可靠，只能靠已记录的 completion_method。

### 5.5 指数退避重试

**退避序列：** [1, 5, 30, 120] 分钟

```
第 1 次失败 → 等 1 分钟
第 2 次失败 → 等 5 分钟
第 3 次失败 → 等 30 分钟
第 4 次及以后 → 等 120 分钟
成功 → 重置 retry_count=0
```

**为什么需要？**

服务端挂掉时，避免每次插件启动都打它，造成雪崩。

### 5.6 容错设计

**单条失败不影响整批：**
```java
for (WorkflowItem item : wfItems) {
    try {
        saveWorkflow(item, ...);
    } catch (Exception e) {
        log.error("save workflow failed", e);
        resp.reject(item.getWorkflowId(), "internal_error");
    }
}
```

**没有全局事务：**
- 一条脏数据不该阻塞整批
- 客户端未被确认的记录会重试


## 六、部署与配置

### 6.1 服务端部署

**前置条件：**
- MySQL 8.0 或 DM8 达梦数据库
- zhisheng-interact-admin 服务已部署

**部署步骤：**

1. **执行建表 DDL**
   ```bash
   mysql -h <host> -u <user> -p <database> < basic/src/main/resources/sql/avatar_telemetry.sql
   ```

2. **编译部署**
   ```bash
   cd D:/codeRep/codeRep-zhisheng
   mvn clean package -pl basic,zhisheng-interact-admin -am -DskipTests
   # 产物在 zhisheng-interact-admin/target/
   # 按既有流程部署到 Kubernetes
   ```

3. **验证**
   ```bash
   curl http://<host>:13042/zs_admin/avatarTelemetry/workflowStat
   # 期望返回: {"flag":true,"code":0,"data":{...}}
   ```

### 6.2 客户端配置

**修改上报端点：**

编辑 `~/.claude/skills/avatar-platform/config/telemetry.json`：
```json
{
  "endpoint": "https://your-domain.com/zs_admin/avatarTelemetry/report",
  "timeout_ms": 5000,
  "batch_size": 50,
  "retry_backoff_minutes": [1, 5, 30, 120]
}
```

**自动化上传（四重触发，全部由钩子驱动）：**

| 触发时机 | 说明 | 门槛 |
|---|---|---|
| 1. 入口 skill 调用 | 用户开始新任务时清空历史积压 | 积压 ≥ 3 或距上次 > 30 分钟 |
| 2. 平台工具调用后 | `xfyun_*.py` 等执行完顺手上传 | 同上 |
| 3. SessionEnd | 会话正常结束 | 无门槛，无条件上传 |
| 4. 新会话补偿收口 | 发现遗留 in_progress 工作流时 | 积压 ≥ 3 或距上次 > 30 分钟 |

**设计约束：不使用任何常驻定时任务。**

上报只发生在用户实际使用插件期间，插件卸载后机器上不留任何后台活动、不残留计划任务。
代价是最后一批数据可能滞留到下次使用插件时才上传 —— 使用统计无实时性要求，可接受。

上传器由钩子通过 `subprocess.Popen(start_new_session=True)` 后台拉起，不阻塞会话。

**手动触发上传：**
```bash
python ~/.claude/skills/avatar-platform/tools/uploader.py
```

### 6.3 用户体验

**安装：**
```bash
/skill add avatar-platform
```

**使用：**
- 用户正常使用插件
- hook 自动触发、自动落本地库
- **无需安装任何依赖**（Python 标准库）
- 数据存储在 `~/.claude/avatar-platform/telemetry/telemetry.db`

**上报：**
- 当前需手动运行 `uploader.py`
- 用户无感知（后台进程）

## 七、数据安全与合规

### 7.1 匿名化处理

| 原始数据 | 匿名化方式 | 可逆性 |
|---|---|---|
| Windows MachineGuid | SHA-256 截断前 16 位 | ✗ 不可逆 |
| 讯飞 appId | SHA-256 截断前 16 位 | ✗ 不可逆 |
| session_id | 直接使用（Claude Code 生成） | △ 内部标识，非用户信息 |
| 本地路径 | completion_detail 可能包含 | △ 截断到 1000 字符 |

**匿名 ID 示例：**
```
MachineGuid: {12345678-1234-1234-1234-123456789012}
SHA-256: a1b2c3d4e5f6...（64 字符）
截断: a1b2c3d4e5f6a7b8（16 字符）
加前缀: anon_a1b2c3d4e5f6a7b8
```

**碰撞概率：**
- 16 位十六进制 = 64 bit = 1.8×10^19 种取值
- 生日碰撞公式：50% 概率需要 54 亿设备
- 实际量级：几千到几万设备
- **碰撞概率可忽略**

### 7.2 数据最小化

**只收集必要字段：**

| 字段 | 用途 | 是否必需 |
|---|---|---|
| anonymous_id | 设备去重、趋势分析 | ✓ |
| xfyun_user_id | 账号去重、登录率 | ✓ |
| workflow_type | 功能偏好分析 | ✓ |
| skill_name | 使用频次统计 | ✓ |
| completion_* | 完成率、故障分析 | ✓ |
| os / plugin_version | 兼容性分析 | △ 可选 |

**不收集：**
- 用户真实姓名、手机号、邮箱
- 完整文件路径（截断到 1000 字符）
- 代码内容
- 对话历史

### 7.3 安全措施

**传输安全：**
- 生产环境建议使用 HTTPS
- 当前配置示例用 HTTP（内网环境）

**访问控制：**
- 上报接口当前无鉴权（依赖网络隔离）
- 如暴露公网，建议加共享密钥验证

**数据保留：**
- 建议服务端保留 90 天
- 客户端本地已上传数据可删除（未实现自动清理）

### 7.4 合规要点

**用户同意：**
- avatar-workflow-entry 在业务路由前检查授权状态
- 只有完整声明和用户明确同意才采集、建库和上传
- 未决定、旧版同意、拒绝或撤回均保持关闭
- 拒绝不影响插件业务功能，且不会反复询问

**数据主体权利：**
- 查询权：通过 anonymous_id 查询（需实现）
- 删除权：DELETE WHERE anonymous_id=?（需实现）
- 撤回同意：停止采集和上报，删除本地遥测数据；服务端删除方式由正式声明提供

**跨境传输：**
- 数据是否出境？（取决于服务端部署位置）
- 如出境需额外告知和同意

## 八、监控与运维

### 8.1 关键指标

**客户端：**
- uploaded=0 的记录数（积压量）
- retry_count（连续失败次数）
- 本地库大小

**服务端：**
- 上报成功率（acceptedIds / totalIds）
- 平均响应时间
- rejected 记录数及原因分布

### 8.2 故障排查

**客户端问题：**

| 现象 | 可能原因 | 排查方法 |
|---|---|---|
| 无本地数据 | hook 未触发 / 无业务意图 | 检查 has_avatar_signal |
| 数据无法上传 | 端点配置错误 / 网络不通 | --dry-run 查看报文 |
| 持续退避 | 服务端 500 / 超时 | 检查 upload_state.json |

**服务端问题：**

| 现象 | 可能原因 | 排查方法 |
|---|---|---|
| 大量 rejected | 校验规则过严 / 字段不匹配 | 查日志 rejected 原因 |
| 数据重复 | 幂等失效 | 检查 workflow_id 去重逻辑 |
| 统计数字偏大 | 噪声过滤失效 | 检查 has_avatar_signal/side_effect |

### 8.3 容量规划

**假设：**
- 日活 1000 设备
- 每设备每天 5 个工作流
- 每工作流 3 个 skill 调用

**日增数据量：**
- workflows: 5000 行 × 1KB = 5MB
- invocations: 15000 行 × 0.5KB = 7.5MB
- **合计: 12.5MB/天**

**90 天存储：**
- 12.5MB × 90 = 1.125GB
- 索引开销约 2 倍 = **2.25GB**

**并发：**
- 高峰 QPS < 10（批量上报，非实时）
- 单次处理 100 条记录 < 1 秒

## 九、后续优化方向

### 9.1 功能增强

1. **自动化上传**
   - SessionEnd 时触发
   - 或后台定时任务（每小时）

2. **用户主动查询**
   - 提供 Web 界面或命令行工具
   - 用户可查看自己的使用统计

3. **异常告警**
   - 完成率骤降告警
   - 高频故障场景告警

4. **跨会话恢复（已实现）**
   - 同匿名设备、同 cwd、最近活动在 5 分钟内、无完成证据且状态为 `in_progress/interrupted` 时接续
   - 新 session 映射到原 workflow ID，不生成服务端合并字段

### 9.2 性能优化

1. **批量插入优化**
   - 当前逐条 INSERT/UPDATE
   - 可改为 BATCH INSERT（100 条/次）

2. **统计接口缓存**
   - Redis 缓存统计结果（5 分钟）
   - 减少数据库压力

3. **异步处理**
   - 上报接口写消息队列
   - 异步消费入库

### 9.3 数据价值挖掘

1. **用户画像**
   - 按使用频次分层（重度/轻度）
   - 按功能偏好分类（SDK 派/模板派）

2. **漏斗分析**
   - 从进入到完成的流程漏斗
   - 识别流失环节

3. **A/B 测试支撑**
   - 按 plugin_version 对比完成率
   - 评估新功能效果

## 十、总结

### 10.1 技术亮点

1. **三层幂等** — 保证统计不重复
2. **五重触发上传** — 实时性高、容错性强
   - 关键节点实时上传（入口点、平台工具）
   - SessionEnd 主路径
   - 补偿收口容错
   - 定时任务兜底
   - 智能节流（积压 >= 10 才触发）
3. **完成判定分级** — 区分硬证据和自报
4. **补偿收口机制** — 最终一致性保证
5. **简化过滤逻辑** — 只保留 has_avatar_signal，逻辑清晰
6. **零依赖部署** — Python 标准库，用户无感知

### 10.2 业务价值

1. **指导迭代优先级** — 发现高频和冷门功能
2. **优化用户体验** — 定位卡点和故障场景
3. **支撑运营决策** — 评估推广效果、用户规模
4. **数据驱动改进** — 完成率、故障场景、接入路径偏好

### 10.3 交付清单

**服务端：**
- ✓ 13 个 Java 类（Controller / Service / Mapper / Domain / DTO）
- ✓ 2 张数据库表（DDL 兼容 MySQL 和 DM8）
- ✓ 7 个统计接口（含 4 个运营分析接口）
- ✓ 编译通过（mvn compile SUCCESS）

**客户端：**
- ✓ 7 个 Python 模块（tracker / telemetry / uploader / completion_check）
- ✓ SQLite 本地库自动创建
- ✓ 28 项测试验证（契约对齐、校验逻辑、上传链路、幂等性）
- ✓ 0 个第三方依赖（纯标准库）

**文档：**
- ✓ 技术设计文档（本文档）
- ✓ 字段说明文档（telemetry-design.md）
- ✓ 用户指南（telemetry.md）

---

**文档版本：** 1.0  
**最后更新：** 2026-08-04  
**编写人：** Claude (Kiro)  
**审核人：** （待填写）
