# iflytek-digital-human 插件使用统计设计文档

> 历史方案：本文记录切换前的 SQLite 设计，已被 `state.json + 异步 Webhook` 当前实现替代。当前设计以 [telemetry-architecture-and-validation.md](telemetry-architecture-and-validation.md) 为准。

## 一、方案概述

### 1.1 设计目标

为讯飞虚拟人 Claude Code 插件建立使用统计，回答三个核心问题：

1. **每个 skill 的使用次数** — 用户最常用哪些功能
2. **工作流是否跑完** — 任务完成率多高、失败在哪
3. **有多少用户在使用** — 设备数、活跃账号数

### 1.2 架构

```
┌─────────────────┐     hook 触发      ┌──────────────────┐
│  Claude Code    │ ─────────────────> │  tracker.py      │
│  (用户会话)      │   每次 Read/Write  │  (本地落库)       │
└─────────────────┘   每轮 prompt      └──────────────────┘
                                              │ SQLite
                                              ▼
┌─────────────────┐                    ┌──────────────────┐
│  uploader.py    │ ◀── Prompt/Stop/终态 │ 本地 telemetry.db│
│  (HTTP 客户端)   │                    └──────────────────┘
└─────────────────┘
        │ POST /zs_admin/avatarTelemetry/report
        ▼
┌─────────────────────────────────────────────────────────┐
│  zhisheng-interact-admin (Spring Boot)                  │
│  ┌─────────────────┐    ┌──────────────────────────┐   │
│  │ Controller      │───>│ Service (幂等去重)        │   │
│  └─────────────────┘    └──────────────────────────┘   │
│                                  │                       │
│                                  ▼                       │
│                          ┌──────────────────┐           │
│                          │  MySQL / DM8     │           │
│                          │  avatar_telemetry│           │
│                          └──────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

**关键设计：边进行边上报、本地幂等、服务端幂等、容错优先**

## 二、数据模型

### 2.1 核心概念

**工作流 (Workflow)** — 一个完整的用户任务，不与 Claude Code 会话强绑定。
- 一个工作流可能调用多个 skill
- 一个工作流可能跨多次上报（边进行边报）
- 主键：首次由 `session_id` 生成；满足 5 分钟接续条件的新 session 继续使用原 ID

**调用记录 (Invocation)** — 工作流内对某个 skill 的使用记录。
- 同一 skill 在同一工作流内多次调用会折叠为一条，`hit_count` 累加
- 主键：`invocation_id`（客户端生成）
- 幂等键：`(workflow_id, skill_name)` —— 服务端用这个去重

### 2.2 字段详解

#### `avatar_telemetry_workflow` 表

| 字段 | 类型 | 必填 | 含义 | 备注 |
|---|---|---|---|---|
| `workflow_id` | varchar(64) | ✓ | 工作流唯一标识 | 首次由 Claude Code session_id 生成；跨会话接续时保持不变。<br>客户端生成，服务端据此幂等 |
| `workflow_type` | varchar(64) | | 工作流类型 | `sdk_integration` / `web_template` / `live_streaming` /<br>`webapi_protocol` / `knowledge_base` / `troubleshoot` /<br>`credentials_setup` / `model_config`。<br>根据首次命中的 skill 推断，可能为空（纯浏览） |
| `agent` | varchar(32) | ✓ | 客户端来源 | 默认来自当前分发包（`claude` / `cursor` / `codex`）；可用 `IFLYTEK_DIGITAL_HUMAN_AGENT` 覆盖。AStudio 等兼容宿主复用包时应上报宿主名。该字段不表示模型名称 |
| `anonymous_id` | varchar(64) | ✓ | 匿名设备标识 | Windows MachineGuid SHA-256 前 16 位（`anon_` 前缀）。<br>不可反推，跨应用追踪能力已断 |
| `xfyun_user_id` | varchar(64) | | 讯飞账号哈希 | 用户登录讯飞开放平台后，从凭据文件读 appId SHA-256<br>前 16 位（`xf_` 前缀）。未登录为 NULL |
| `started_at` | datetime | ✓ | 工作流开始时间 | UTC，精确到毫秒。客户端第一次建行时写入，<br>用于判定产物 mtime 是否晚于开始时间 |
| `ended_at` | datetime | | 工作流结束时间 | UTC，精确到毫秒。<br>**可为 NULL** — `in_progress` 状态的行上传时还没结束 |
| `status` | varchar(32) | ✓ | 工作流状态 | `in_progress` — 进行中<br>`completed` — 已完成<br>`failed` — 失败<br>`interrupted` — 中断（SessionEnd 触发但无完成证据） |
| `has_avatar_signal` | tinyint(1) | ✓ | 是否有业务意图信号 | 1 = 命中斜杠命令 / Skill 调用 / 关键词<br>0 = 纯浏览、开发插件本身<br>**统计口径必须 = 1** |
| `has_real_side_effect` | tinyint(1) | ✓ | 是否有实际产出 | 1 = Write 了插件目录外的文件 / 跑了构建命令<br>0 = 只改了插件源码、只读不写<br>**统计口径必须 = 1** |
| `completion_method` | varchar(32) | | 完成判据 | `artifact` — APK / dist 产物验证通过<br>`verification_flag` — 7 层验证结果文件<br>`artifacts_file` — 平台侧交付物 ID 已落盘<br>`none` / NULL — 什么都没找到 |
| `completion_confidence` | varchar(16) | | 完成证据的可信度 | `high` — 机器验证的产物（APK ZIP 校验 / 7 层验证）<br>`medium` — 有交付物 ID，但本地没实物<br>NULL — 未完成或判据为 `none` |
| `completion_detail` | varchar(1000) | | 命中的产物证据 | JSON 文本，记录具体证据。例如：<br>`{"apk": "path/to.apk", "size": 12345}`<br>`{"template_url": "https://..."}`<br>服务端截断到 1000 字符 |
| `os` | varchar(32) | | 操作系统 | `win32` / `darwin` / `linux`，来自 Python `sys.platform` |
| `plugin_version` | varchar(32) | | 插件版本 | 运行时按插件 manifest/package.json 解析；支持 `IFLYTEK_DIGITAL_HUMAN_PLUGIN_VERSION` 显式覆盖，解析失败时使用包内兜底版本 |
| `schema_version` | varchar(16) | ✓ | 上报协议版本 | 当前为 `1.2`，用于后续兼容处理 |
| `report_time` | datetime | ✓ | 服务端接收时间 | 服务端写入，与 `started_at` 的差距反映上报延迟 |
| `create_time` | datetime | ✓ | 数据库创建时间 | 服务端写入 |
| `update_time` | datetime | ✓ | 数据库更新时间 | 服务端写入，同一工作流多次上报会更新 |

#### `avatar_telemetry_invocation` 表

| 字段 | 类型 | 必填 | 含义 | 备注 |
|---|---|---|---|---|
| `invocation_id` | varchar(64) | ✓ | 调用记录唯一标识 | `inv_` + UUID v4.hex。客户端生成。<br>**服务端不用它去重**（见幂等性设计） |
| `workflow_id` | varchar(64) | ✓ | 所属工作流 | 外键指向 `avatar_telemetry_workflow.workflow_id` |
| `skill_name` | varchar(128) | ✓ | skill 全名 | 如 `avatar-workflow-entry` / `avatar-web-template`。<br>带项目前缀：`iflytek-digital-human:avatar-xxx` |
| `anonymous_id` | varchar(64) | ✓ | 匿名设备标识 | 冗余自 workflow，便于按设备聚合调用 |
| `source` | varchar(32) | ✓ | 调用来源 | `slash` — 用户在输入框敲 `/iflytek-digital-human:xxx`<br>`skill_tool` — 模型调用 Skill 工具<br>`read` — Read 了 `skill.md` 文件 |
| `hit_count` | int | ✓ | 同一工作流内命中次数 | 客户端本地已折叠。服务端幂等更新时取较大值，<br>**不累加**（累加会在重传时翻倍） |
| `first_at` | datetime | ✓ | 首次命中时间 | UTC，精确到毫秒 |
| `last_at` | datetime | ✓ | 末次命中时间 | UTC，精确到毫秒。单次调用时等于 `first_at` |
| `report_time` | datetime | ✓ | 服务端接收时间 | 服务端写入 |
| `create_time` | datetime | ✓ | 数据库创建时间 | 服务端写入 |
| `update_time` | datetime | ✓ | 数据库更新时间 | 服务端写入 |

**唯一键约束**：`UNIQUE(workflow_id, skill_name)` — 服务端幂等依据

## 三、幂等性设计

### 3.1 为什么需要三层幂等

**场景**：
- 同一会话内 hook 触发几十次，都要写同一个 workflow
- SessionEnd 不可靠，会话结束后可能再次上报
- 网络失败重传、用户重装插件后历史数据重传
- 服务端不能因为重传就把统计数字翻倍

### 3.2 客户端本地幂等

**实现：SQLite 主键 + REPLACE**

```sql
-- 工作流表主键
PRIMARY KEY (workflow_id)

-- 调用记录唯一键
UNIQUE (workflow_id, skill_name)
```

**写入策略**：
- 工作流：`REPLACE INTO workflows (...)`，同一 `workflow_id` 后到覆盖先到
- 调用记录：先查 `(workflow_id, skill_name)` 是否存在，存在则累加 `hit_count`、更新 `last_at`

**效果**：同一会话内无论触发多少次，本地只有一条 workflow 行、每个 skill 一条 invocation 行

### 3.3 客户端上传幂等

**实现：服务端确认机制**

上传器发送：
```json
{
  "workflows": [{"workflowId": "wf_abc", ...}],
  "invocations": [{"invocationId": "inv_xyz", ...}]
}
```

服务端响应：
```json
{
  "acceptedWorkflowIds": ["wf_abc"],
  "acceptedInvocationIds": ["inv_xyz"],
  "rejected": []
}
```

**客户端行为**：
```python
mark_uploaded(conn, accepted_wf_ids, accepted_inv_ids)
# 只清理被确认的记录，未确认的留待下次重试
```

**防止的问题**：
- 网络超时 → 服务端收到了但客户端没收到响应 → 客户端重传 → 服务端幂等去重
- 部分接收 → 工作流写入成功、调用记录因校验失败被拒 → 客户端只清理工作流，调用记录下次重传

### 3.4 服务端幂等

#### 工作流幂等

**主键**：`workflow_id`（客户端首次按 `wf_` + session_id 生成，跨会话接续时保持不变）

**策略**：
```java
AvatarTelemetryWorkflow existing = workflowService.getById(id);
if (existing == null) {
    row.setCreateTime(now);
    workflowService.save(row);  // INSERT
} else {
    // 已终结的状态不被 in_progress 回退覆盖
    if ("in_progress".equals(status) && !"in_progress".equals(existing.getStatus())) {
        resp.getAcceptedWorkflowIds().add(id);
        return;  // 确认接收，但不覆盖
    }
    row.setCreateTime(existing.getCreateTime());
    workflowService.updateById(row);  // UPDATE
}
resp.getAcceptedWorkflowIds().add(id);
```

**特殊处理**：
- 补偿收口可能导致乱序上报（先收到 `completed`，后收到 `in_progress`）
- 保护规则：已终结的（completed / failed / interrupted）不被 `in_progress` 回退

#### 调用记录幂等

**幂等键**：`(workflow_id, skill_name)`，而非 `invocation_id`

**为什么不用 invocation_id？**

客户端本地库若被删除重建，同一次调用会生成新的 `invocation_id`：
```python
invocation_id = 'inv_' + uuid.uuid4().hex  # 每次生成都不同
```

如果服务端用 `invocation_id` 去重，会撞 `UNIQUE(workflow_id, skill_name)` 约束报错。

**实现**：
```java
QueryWrapper<AvatarTelemetryInvocation> q = new QueryWrapper<>();
q.eq("workflow_id", item.getWorkflowId()).eq("skill_name", item.getSkillName());
AvatarTelemetryInvocation existing = invocationService.getOne(q, false);

if (existing == null) {
    row.setInvocationId(id);
    invocationService.save(row);
} else {
    // hitCount 取较大值而非累加 — 客户端上报的是累计值，累加会翻倍
    row.setInvocationId(existing.getInvocationId());  // 保持旧 id
    if (existing.getHitCount() > row.getHitCount()) {
        row.setHitCount(existing.getHitCount());
    }
    invocationService.updateById(row);
}
```

**hitCount 不累加的原因**：

客户端上报的已经是该工作流内的累计值：
```python
# 客户端本地折叠
c.execute('UPDATE invocations SET hit_count = hit_count + 1, last_at = ? WHERE ...')
```

如果服务端再累加，重传一次数字就翻一倍。

### 3.5 幂等性验证

实测场景覆盖：

| 场景 | 期望 | 实测 |
|---|---|---|
| 同一会话触发 20 次 hook | 本地 1 条 workflow | ✓ |
| 同一 skill 调用 3 次 | 本地 1 条 invocation，hit_count=3 | ✓ |
| 上传成功后再次上传 | "nothing to upload" | ✓ |
| 服务端 500，数据保留 | uploaded=0 不变，下次重试 | ✓ |
| 部分接收（工作流收、调用拒） | 工作流标记 uploaded=1，调用保留 uploaded=0 | ✓ |
| 重传同一 workflow_id | 服务端 UPDATE 而非 INSERT | ✓（契约测试） |
| 本地库删除重建后重传 | invocation_id 虽变，但 (workflow_id, skill_name) 去重 | ✓（设计验证） |


## 四、完成判定机制

### 4.1 completion_method 详解

记录"**靠什么**判定工作流完成"，优先级从高到低：

| method | 判定逻辑 | 证据强度 |
|---|---|---|
| `verification_flag` | `.runtime/verification-result.json` 新鲜且 `ready_to_deliver: true` | 最强 — SDK 静态与运行验证全通过 |
| `artifact` | 凭据 workflow 的固定 `.env` 含所需键；不读取或记录值 | 强 — 固定产物 |
| `artifacts_file` | 非 SDK workflow 的 `.runtime/artifacts.json` 含 `template_url` / `live_url` / `lib_id` | 中 — 有交付物 ID，但本地无实物 |
| `none` | 什么都没找到 | 无 — 通常伴随 `interrupted` |

**扫盘顺序**：按上表从上到下，命中第一个就停。

**APK 验证细节**：
```python
def check_apk(apk_path, since_epoch):
    if not apk_path.is_file():
        return None
    if apk_path.stat().st_mtime < since_epoch:
        return None  # 上次构建残留
    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            names = set(z.namelist())
            if 'AndroidManifest.xml' not in names:
                return None
            if not any(n.startswith('classes') and n.endswith('.dex') for n in names):
                return None
        return ('artifact', 'high', {'apk': str(apk_path), 'size': apk_path.stat().st_size})
    except zipfile.BadZipFile:
        return None  # 假文件
```

### 4.2 completion_confidence 详解

记录"**多可信**"，与 method 的映射：

| confidence | 含义 | 对应 method |
|---|---|---|
| `high` | 机器验证过的产物，无法伪造 | `verification_flag` / `artifact` |
| `medium` | 有交付物 ID，但本地没实物 | `artifacts_file` |
| NULL | 未完成或判据为 `none` | `none` / 进行中 |

**为什么要分 high/medium/low？**

统计"完成率"时给两个数字：
- **宽口径** (`completionRateWide`) — 只要 `status=completed` 就算，含自报
- **硬证据** (`completionRateHard`) — 只算 `completion_confidence=high` 的

两者的差距就是**自报数据占多少**。差距大说明数据不扎实。

### 4.3 completion_detail 示例

JSON 文本，记录具体证据：

**APK 产物**：
```json
{
  "apk": "<project-root>/app/build/outputs/apk/debug/app-debug.apk",
  "size": 12589327
}
```

**Web 构建产物**：
```json
{
  "dist_dir": "<project-root>/dist",
  "html_files": 3,
  "has_bundled_assets": true
}
```

**7 层验证结果**：
```json
{
  "verification_file": ".runtime/verification_results.json",
  "ready_to_deliver": true
}
```

**平台侧交付物**：
```json
{
  "template_url": "https://virtual-man.xfyun.cn/...",
  "template_id": "tpl_abc123"
}
```

服务端截断到 1000 字符（防止路径过长撑爆字段）。

### 4.4 完成判定的三个时机

| 时机 | 触发者 | 写入哪些字段 |
|---|---|---|
| **机会性扫盘** | hook tracker，每轮 prompt | `completion_method` / `completion_confidence` / `completion_detail`<br>**不改 status** — 还在进行中 |
| **Reporter 自报** | skill 调用 `telemetry.py complete` | SDK 必须先命中新鲜 `verification_flag`，否则拒绝并保持 `in_progress`；其他类型再按证据升级 |
| **补偿收口** | 下次会话启动，清理 30 分钟前遗留的 `in_progress` | `status=completed/interrupted`，根据扫盘结果 |

**为什么机会性扫盘不改 status？**

产物可能在会话中途就出现了（构建完成），但用户还在继续操作（调试、发布）。此时记下 `completion_method=artifact`，但 `status` 保持 `in_progress`，等 SessionEnd 或 Reporter 自报才置 `completed`。

**已有硬证据时不重复扫**：
```python
HARD = ('artifact', 'verification_flag', 'artifacts_file')
if existing_method in HARD:
    method, conf, detail = existing_method, None, {}
else:
    method, conf, detail = detect(cwd, started_at, wf_type)
```

防止每轮 prompt 都跑一次 APK ZIP 校验（几十 MB 的文件，性能开销）。


## 五、服务端接口

### 5.1 上报接口

**POST** `/zs_admin/avatarTelemetry/report`

**请求体**：
```json
{
  "schemaVersion": "1.0",
  "anonymousId": "anon_900bb23c914eecfa",
  "workflows": [
    {
      "workflowId": "wf_5efb68bf-7a22-4356-b4ad-0bc7bef0e871",
      "workflowType": "sdk_integration",
      "anonymousId": "anon_900bb23c914eecfa",
      "xfyunUserId": "xf_9ec92fb74293445d",
      "startedAt": "2026-08-04T06:17:23.398Z",
      "endedAt": "2026-08-04T06:18:30.102Z",
      "status": "completed",
      "hasAvatarSignal": 1,
      "hasRealSideEffect": 1,
      "completionMethod": "artifact",
      "completionConfidence": "high",
      "completionDetail": "{\"apk\": \"...\", \"size\": 12589327}",
      "os": "win32",
      "pluginVersion": "1.1.0"
    }
  ],
  "invocations": [
    {
      "invocationId": "inv_a6c3eb1250204d45",
      "workflowId": "wf_5efb68bf-7a22-4356-b4ad-0bc7bef0e871",
      "skillName": "iflytek-digital-human:avatar-verification",
      "anonymousId": "anon_900bb23c914eecfa",
      "source": "skill_tool",
      "hitCount": 2,
      "firstAt": "2026-08-04T06:17:25.000Z",
      "lastAt": "2026-08-04T06:18:10.500Z"
    }
  ]
}
```

**响应**（成功）：
```json
{
  "flag": true,
  "code": 0,
  "desc": "success",
  "data": {
    "acceptedWorkflowIds": ["wf_5efb68bf-7a22-4356-b4ad-0bc7bef0e871"],
    "acceptedInvocationIds": ["inv_a6c3eb1250204d45"],
    "rejected": []
  }
}
```

**响应**（部分拒绝）：
```json
{
  "flag": true,
  "code": 0,
  "desc": "success",
  "data": {
    "acceptedWorkflowIds": ["wf_abc"],
    "acceptedInvocationIds": [],
    "rejected": [
      {"id": "inv_xyz", "reason": "source_invalid"}
    ]
  }
}
```

**校验规则**：

工作流必填项：
- `workflowId` 非空
- `anonymousId` 非空
- `startedAt` 非空且格式合法（ISO8601 UTC）
- `status` ∈ {`in_progress`, `completed`, `failed`, `interrupted`}
- `completionConfidence`（如果非空）∈ {`high`, `medium`, `low`}

调用记录必填项：
- `invocationId` 非空
- `workflowId` 和 `skillName` 非空
- `anonymousId` 非空
- `source` ∈ {`slash`, `skill_tool`, `read`}
- `firstAt` 非空且格式合法

**容错设计**：
- 单条记录校验失败不影响其他记录
- 每条独立 try/catch，异常记录放入 `rejected`
- 没有全局事务 — 一条脏数据不该阻塞整批

### 5.2 统计接口

#### skill 使用统计

**GET** `/zs_admin/avatarTelemetry/skillUsage?startTime=<ms>&endTime=<ms>`

**参数**：
- `startTime` / `endTime` — 毫秒时间戳，可选，默认全量

**响应**：
```json
{
  "flag": true,
  "code": 0,
  "desc": "success",
  "data": {
    "records": [
      {
        "skillName": "avatar-verification",
        "workflowCount": 12,
        "rawHits": 35
      },
      {
        "skillName": "avatar-web-template",
        "workflowCount": 8,
        "rawHits": 10
      }
    ],
    "total": 15
  }
}
```

**含义**：
- `workflowCount` — 有多少个工作流用过这个 skill（去重）
- `rawHits` — 原始命中次数总和（`SUM(hit_count)`）

**统计口径**：只统计 `has_avatar_signal=1 AND has_real_side_effect=1` 的工作流

#### 工作流完成统计

**GET** `/zs_admin/avatarTelemetry/workflowStat?startTime=<ms>&endTime=<ms>`

**响应**：
```json
{
  "flag": true,
  "code": 0,
  "desc": "success",
  "data": {
    "total": 100,
    "completedWide": 67,
    "completedHard": 45,
    "interrupted": 20,
    "failed": 5,
    "inProgress": 8,
    "completionRateWide": "67.0%",
    "completionRateHard": "45.0%",
    "byType": [
      {
        "workflowType": "sdk_integration",
        "total": 50,
        "completed": 35,
        "completionRate": "70.0%"
      }
    ],
    "byCompletionMethod": {
      "artifact": 30,
      "verification_flag": 15,
      "artifacts_file": 22
    }
  }
}
```

**含义**：
- `completedWide` — 所有 `status=completed` 的（含自报）
- `completedHard` — 只算 `completion_confidence=high` 的（硬证据）
- 两者的差距反映自报数据占比

#### 用户规模统计

**GET** `/zs_admin/avatarTelemetry/userStat?startTime=<ms>&endTime=<ms>`

**响应**：
```json
{
  "flag": true,
  "code": 0,
  "desc": "success",
  "data": {
    "deviceCount": 85,
    "deviceCountRaw": 142,
    "xfyunUserCount": 32,
    "workflowCount": 100,
    "byOs": {
      "win32": 60,
      "darwin": 20,
      "linux": 5
    },
    "byPluginVersion": {
      "1.1.0": 85
    }
  }
}
```

**含义**：
- `deviceCount` — 去重后的设备数（经过噪声过滤）
- `deviceCountRaw` — 未过滤的设备数（评估过滤规则砍掉多少）
- `xfyunUserCount` — 登录过讯飞平台的账号数（`xfyun_user_id` 去重）


## 六、客户端方法

### 6.1 核心模块

| 文件 | 职责 |
|---|---|
| `hooks/tracker.py` | Hook 入口，落本地库，机会性扫盘 |
| `tools/telemetry.py` | Reporter 自报接口（`complete` / `fail`） |
| `tools/telemetry_common.py` | 共用工具（数据库连接、匿名化、时间格式化） |
| `tools/completion_check.py` | 产物扫盘逻辑（APK / dist / artifacts.json） |
| `tools/uploader.py` | HTTP 上传器，指数退避重试 |
| `tools/init_db.py` | 初始化本地数据库 |
| `config/telemetry.json` | 配置文件（端点地址、批量大小、重试间隔） |

### 6.2 数据流

```
┌─────────────────────────────────────────────────────┐
│  Claude Code hook 触发                              │
│  (UserPromptSubmit / PreToolUse / Stop / SessionEnd)│
└─────────────────────────────────────────────────────┘
                    │ JSON payload via stdin
                    ▼
┌─────────────────────────────────────────────────────┐
│  hooks/tracker.py                                   │
│  ┌────────────────┐   ┌────────────────────────┐   │
│  │ 提取 session_id│──>│ 判定 workflow_type     │   │
│  │ 匿名化设备标识 │   │ (按首个命中 skill)     │   │
│  └────────────────┘   └────────────────────────┘   │
│                              │                       │
│                              ▼                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ REPLACE INTO workflows (...)                │   │
│  │ UPDATE invocations SET hit_count = ... ON   │   │
│  │   CONFLICT (workflow_id, skill_name)        │   │
│  └─────────────────────────────────────────────┘   │
│                              │                       │
│                 prompt / end │                       │
│                              ▼                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ 机会性扫盘 (completion_check.detect)        │   │
│  │ - 检查 APK / dist / verification_results    │   │
│  │ - 写 completion_method / confidence         │   │
│  │ - 不改 status (还在进行中)                  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                    │ SQLite
                    ▼
┌─────────────────────────────────────────────────────┐
│  ~/.claude/iflytek-digital-human/telemetry/telemetry.db  │
│  - workflows (uploaded=0)                           │
│  - invocations (uploaded=0)                         │
└─────────────────────────────────────────────────────┘
                    │ Prompt 首报 / Stop 补传 / 终态强制重传
                    ▼
┌─────────────────────────────────────────────────────┐
│  tools/uploader.py                                  │
│  ┌────────────────┐   ┌────────────────────────┐   │
│  │ 退避检查       │──>│ collect(uploaded=0)    │   │
│  │ (指数退避)     │   │ 构造 JSON payload      │   │
│  └────────────────┘   └────────────────────────┘   │
│                              │                       │
│                              ▼                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ POST /zs_admin/avatarTelemetry/report       │   │
│  │ 解析 acceptedWorkflowIds / acceptedInvo... │   │
│  └─────────────────────────────────────────────┘   │
│                              │                       │
│                              ▼                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ UPDATE workflows SET uploaded=1             │   │
│  │   WHERE workflow_id IN (accepted)           │   │
│  │ 未确认的保持 uploaded=0，下次重试          │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 6.3 关键方法

#### `tracker.py::handle_prompt`
```python
def handle_prompt(payload, conn):
    session_id = payload.get('session_id')
    wf_id = active_workflow_id(conn, session_id)
    
    # 业务意图判定
    if not has_avatar_intent(payload):
        return  # 不建行
    
    # 建行或接续：最近活动命中 5 分钟规则时返回原 workflow_id
    wf_id = ensure_workflow(conn, wf_id, anonymous_id, signal=True,
                            cwd=payload.get('cwd'), session_id=session_id)
    
    # 记录 skill 调用
    for skill in extract_skills(payload):
        c.execute('''
            INSERT INTO invocations (invocation_id, workflow_id, skill_name, ...)
            VALUES (?, ?, ?, ...)
            ON CONFLICT(workflow_id, skill_name) DO NOTHING
        ''')
    
    # 机会性扫盘
    method, detail = detect(cwd, started_at, wf_type)
    if method != 'none':
        c.execute('UPDATE workflows SET completion_method=?, ... WHERE workflow_id=?')
```

#### `telemetry.py::complete`
```python
def complete(verify=True, project_dir=None):
    """Reporter 自报完成。skill 收尾调用。"""
    conn = connect()
    session_id, hook_cwd = read_current_session()
    cwd = project_dir or hook_cwd
    wf_id = active_workflow_id(conn, session_id)
    
    method, detail = 'none', {}
    if verify:
        m, d = detect(cwd, started_at, wf_type)
        if m != 'none':
            method, detail = m, d
    
    if wf_type == 'sdk_integration' and method != 'verification_flag':
        return False, 'needs_runtime_verification'

    conn.execute('''
        UPDATE workflows
        SET status = 'completed', ended_at = ?,
            completion_method = ?, completion_detail = ?
        WHERE workflow_id = ?
    ''', (now_iso(), method, json.dumps(detail), wf_id))
    conn.commit()
```

#### `uploader.py::should_attempt`
```python
def should_attempt(cfg, state):
    """指数退避：连续失败后拉长间隔。"""
    last = state.get('last_attempt')
    if not last:
        return True, None
    
    backoff = cfg['retry_backoff_minutes']  # [1, 5, 30, 120]
    retries = state.get('retry_count', 0)
    if retries <= 0:
        wait_min = 0
    else:
        wait_min = backoff[min(retries - 1, len(backoff) - 1)]
    
    elapsed_min = (now - parse(last)).total_seconds() / 60.0
    if elapsed_min < wait_min:
        return False, f'退避中：还需等待 {wait_min - elapsed_min:.1f} 分钟'
    return True, None
```

**退避序列**：第 1 次失败等 1 分钟，第 2 次等 5 分钟，第 3 次等 30 分钟，第 4 次及以后等 120 分钟

#### `completion_check.py::detect`
```python
def detect(root, since_epoch, workflow_type):
    """扫盘，按优先级返回第一个命中的判据。"""
    checks = [
        lambda: check_verification_results(root),
        lambda: check_apk(root, since_epoch),
        lambda: check_web_dist(root, since_epoch),
        lambda: check_artifacts_json(root),
    ]
    for fn in checks:
        result = fn()
        if result:
            return result
    return ('none', 'low', {})
```


## 七、噪声过滤

### 7.1 为什么需要过滤

实测 133 个历史会话，发现 54% 是假阳性：

| 类别 | 占比 | 示例 |
|---|---|---|
| 真实使用 | 46% | 用户提需求、生成代码、构建产物 |
| 纯浏览 | 18% | 只 Read skill.md，没有任何操作 |
| 开发插件本身 | 36% | 改 hook 代码、改文档、调试工具 |

不过滤的话，统计数字膨胀一倍多，完全失真。

### 7.2 两个标记

#### `has_avatar_signal` — 是否有业务意图

**置 1 的条件**（任一命中）：
1. 用户敲了斜杠命令：`/iflytek-digital-human:xxx`
2. 模型调用 Skill 工具：`tool_name='Skill'` 且 `skill` 参数匹配
3. prompt 里有关键词：`虚拟人` / `数字人` / `讯飞` / `xfyun` / `iflytek` / `avatar`

**关键词匹配前的清洗**：
```python
# 剥掉路径、URL、行内代码，避免假阳性
cleaned = re.sub(r'[A-Za-z]:[/\][^\s]*', ' ', prompt)  # C:\path\to\iflytek-digital-human
cleaned = re.sub(r'https?://[^\s]+', ' ', cleaned)      # https://...avatar...
cleaned = re.sub(r'`[^`]+`', ' ', cleaned)               # `avatar` 行内代码
```

**反例**（不置 1）：
- `python <plugin-root>/tools/verify_hooks.py` — 纯路径
- `cat ~/.claude/skills/iflytek-digital-human/skill.md` — 读文件
- 通篇没提业务需求，只是在排查 bug

#### `has_real_side_effect` — 是否有实际产出

**置 1 的条件**（任一命中）：
1. Write / Edit 写了插件目录**之外**的文件
2. 跑了构建命令：`gradlew` / `npm run` / `vite build` 等
3. 跑了平台工具脚本：`xfyun_*.py` / `write_env_safe.py` / `_fetch_creds.py`

**插件目录的判定**：
```python
PLUGIN_ROOT = Path(__file__).resolve().parent.parent  # ~/.claude/skills/iflytek-digital-human
SKILLS_ROOT = PLUGIN_ROOT.parent                       # ~/.claude/skills

def is_plugin_internal(path):
    try:
        p = Path(path).resolve()
        return (p.is_relative_to(PLUGIN_ROOT) or
                p.is_relative_to(SKILLS_ROOT) or
                '.claude' in p.parts)
    except:
        return False
```

**反例**（不置 1）：
- 改 `~/.claude/skills/iflytek-digital-human/hooks/tracker.py` — 开发插件本身
- 改 `~/.claude/skills/other-skill/skill.md` — 开发其他插件
- 只跑了 Read / Grep / Bash 的 `ls` / `cat` — 无副作用

### 7.3 统计口径

服务端创建视图：
```sql
CREATE VIEW clean_workflows AS
SELECT * FROM workflows
WHERE has_avatar_signal = 1 AND has_real_side_effect = 1;
```

三个统计接口全部只查这个视图，**但原始数据保留**。

`userStat` 会额外返回 `deviceCountRaw`（未过滤的设备数），让你看到过滤规则砍掉了多少：
```json
{
  "deviceCount": 85,       // 过滤后
  "deviceCountRaw": 142    // 原始值，砍掉 40%
}
```

### 7.4 已知限制

**会漏的场景**：
- 用户用自然语言提需求，但没提关键词（如"帮我做个 AI 对话机器人"）— 模型调 Skill 工具时才置 1
- 用户只用 Python REPL 调平台 API，不经过 skill — 没有 Skill 调用也没有构建命令

**会误判的场景**（暂未发现实例）：
- 用户在写虚拟人相关的博客，频繁出现"虚拟人"但不是在用插件 — 但如果没有 Write/构建命令，`has_real_side_effect=0` 仍会过滤掉

规则可调：标记落库了，以后规则改了可以重跑历史数据。


## 八、测试验证

### 8.1 测试覆盖

| 类别 | 测试项 | 方法 | 结果 |
|---|---|---|---|
| **契约对齐** | 客户端 JSON 字段名与服务端 DTO 匹配 | Jackson 反序列化，`FAIL_ON_UNKNOWN_PROPERTIES=true` | ✓ 18 项全过 |
| | 响应字段名客户端能识别 | 序列化服务端 DTO，检查字段名 | ✓ |
| **校验逻辑** | 缺必填字段被拒 | 畸形 JSON 喂给复刻的校验规则 | ✓ 7 项 |
| | 枚举值非法被拒 | status/source/confidence 非法值 | ✓ 3 项 |
| | 时间格式非法被拒 | startedAt 格式错误 | ✓ 2 项 |
| | 边界值规整 | hitCount=0 规整为 1 | ✓ |
| | 超长截断 | completionDetail 1500 字截断到 1000 | ✓ |
| **上传链路** | 成功路径 | mock server 模式 ok | ✓ uploaded=1 |
| | 失败保留数据 | mock server 模式 fail | ✓ uploaded=0，retry_count++ |
| | 指数退避 | 连续失败，检查退避间隔 | ✓ 1/5/30/120 分钟 |
| | 部分接收 | mock server 模式 partial | ✓ 工作流确认，调用保留 |
| **幂等性** | 本地同会话多次触发 | 20 次 hook | ✓ 1 条 workflow |
| | 同 skill 多次调用 | 3 次调用 | ✓ 1 条 invocation，hit_count=3 |
| | 重传幂等 | 上传成功后再次上传 | ✓ "nothing to upload" |
| | 服务端幂等 | 同 workflow_id 重传 | ✓ UPDATE 而非 INSERT（设计验证） |
| **完成判定** | APK ZIP 校验 | 假文件（not-a-zip）| ✓ 拒绝，降级 low |
| | mtime 门禁 | 上次构建残留 | ✓ 拒绝 |
| | 已有硬证据不重复扫 | completion_method=artifact | ✓ 不再扫盘 |
| | Reporter 自报被扫盘升级 | `complete(verify=True)` | ✓ 扫到 APK 升 high |
| **噪声过滤** | 路径中的关键词不算 | `C:\iflytek-digital-human\tools\x.py` | ✓ signal=0 |
| | 纯读不建行 | 只 Read skill.md | ✓ 无记录 |
| | 插件目录内的写不算副作用 | Write hooks/tracker.py | ✓ side_effect=0 |
| | 平台脚本算副作用 | `python xfyun_secrets.py` | ✓ side_effect=1 |

### 8.2 未覆盖的场景

**服务端真实联调** — 契约和校验都验了，但没有一次真正的 HTTP 请求打到 Spring Boot 里。需要：
1. 在内网 MySQL 执行建表 DDL
2. 启动 `zhisheng-interact-admin` 服务
3. 运行 `python uploader.py --endpoint http://<host>:13042/zs_admin/avatarTelemetry/report`

**统计接口功能验证** — 服务端跑不起来，三个统计接口（skillUsage / workflowStat / userStat）只验证了编译通过，未实测返回的 JSON 结构。

**长期稳定性** — 本地库在真实环境运行 1 周以上、经历数百次上传、跨多次插件重装的场景未测。

### 8.3 已修复的 bug

| bug | 发现方式 | 影响 | 修复 |
|---|---|---|---|
| 服务端编译失败 | `mvn compile` | `schemaVersion` 在外层请求，却在 `WorkflowItem` 上调 get | 改成从外层透传 |
| 客户端状态判定错 | 实测数据对比 | 机会性扫盘写了 method，handle_end 看到非空跳过重扫，局部变量还是 `'none'` 导致判成 `interrupted` | 已有硬证据时直接复用，不进 detect |
| 退避序列差一位 | 单元测试 | 第 1 次失败等 5 分钟而非 1 分钟 | `backoff[retry_count]` 改成 `backoff[retry_count-1]` |
| 平台脚本副作用不认 | 真实场景回放 | 配凭据那次 13 次 Bash 全判无关，`side_effect=0` 被过滤 | 加 `PLATFORM_TOOL_RE` 匹配 `xfyun_*.py` 等 |
| 路径中关键词假阳性 | 代码审查 | `python .../iflytek-digital-human/tools/x.py` 被当成业务意图 | prompt 匹配前剥掉路径、URL、行内代码 |
| APK 假文件通过验证 | 对抗测试 | 往 APK 路径塞 `not-a-zip` 被判 `artifact` | 加 ZIP 校验 + mtime 门禁 |


## 九、部署与配置

### 9.1 服务端部署

#### 1. 执行建表 DDL

```bash
mysql -h <host> -u <user> -p <database> < basic/src/main/resources/sql/avatar_telemetry.sql
```

DDL 兼容 MySQL 8.0 和 DM8 达梦：
- 无 `ON DUPLICATE KEY UPDATE`（改用程序层幂等）
- 字段类型都是通用的（varchar / datetime / tinyint / int）

#### 2. 编译部署

```bash
cd D:/codeRep/codeRep-zhisheng
mvn clean package -pl basic,zhisheng-interact-admin -am -DskipTests

# 产物在 zhisheng-interact-admin/target/
# 按既有流程部署到 Kubernetes
```

#### 3. 验证

启动后访问：
```bash
curl http://<host>:13042/zs_admin/avatarTelemetry/workflowStat
```

期望返回：
```json
{
  "flag": true,
  "code": 0,
  "data": {"total": 0, "completedWide": 0, ...}
}
```

### 9.2 客户端配置

#### 修改端点地址

编辑 `~/.claude/skills/iflytek-digital-human/config/telemetry.json`：

```json
{
  "endpoint": "https://your-domain.com/zs_admin/avatarTelemetry/report",
  "timeout_ms": 5000,
  "batch_size": 50,
  "retry_backoff_minutes": [1, 5, 30, 120],
  "schema_version": "1.2",
  "retention_days": 7
}
```

**关键参数**：
- `endpoint` — 服务端上报地址（**必须改**）
- `timeout_ms` — HTTP 超时，默认 3 秒
- `batch_size` — 单次上传条数上限，默认 50
- `retry_backoff_minutes` — 失败后的退避序列，默认 [1, 5, 30, 120] 分钟
- `retention_days` — 本地已上传数据保留天数（未实现）

#### 手动触发上传

```bash
python ~/.claude/skills/iflytek-digital-human/tools/uploader.py

# 或指定端点
python ~/.claude/skills/iflytek-digital-human/tools/uploader.py \
  --endpoint https://your-domain.com/zs_admin/avatarTelemetry/report

# 强制绕过退避
python ~/.claude/skills/iflytek-digital-human/tools/uploader.py --force

# 查看将要发送的报文
python ~/.claude/skills/iflytek-digital-human/tools/uploader.py --dry-run
```

### 9.3 自动化上传

- `UserPromptSubmit` 创建或续接有效 workflow 后，提交本地事务并异步首报 `in_progress`。
- `PreToolUse` 的 Skill / Read 只写本地数据库，不直接启动上传器。
- `Stop` 异步补传本轮累计数据；Reporter `complete` / `fail`、`SessionEnd` 和遗留收口
  强制启动上传器，将同一 `workflow_id` 幂等更新为终态。
- 每次实际 POST 前上传器都会重新检查同意状态和声明地址；未同意或声明变为 `stale` 时停止。

### 9.4 监控与日志

#### 客户端诊断日志

```bash
cat ~/.claude/iflytek-digital-human/telemetry/debug.log
```

包含：
- 每次 hook 触发的 payload 摘要
- skill 调用记录
- 扫盘结果
- 数据库操作

**默认关闭**，开启方式：
```python
# tools/telemetry_common.py
DEBUG = True  # 改成 True
```

#### 服务端日志

Spring Boot 标准日志，关键字：
```
avatar telemetry: workflow batch 5 exceeds limit
avatar telemetry: save workflow failed, id=wf_xxx
avatar telemetry: 3 record(s) rejected, first={...}
```

#### 查询本地统计

```bash
python ~/.claude/skills/iflytek-digital-human/tools/telemetry.py stats
```

输出：
```
=== 工作流统计 (最近 7 天) ===
  总数           : 12
  已完成 (宽口径) : 8 (66.7%)
  已完成 (硬证据) : 5 (41.7%)
  中断           : 3
  失败           : 1

=== skill 使用次数 ===
  avatar-verification       : 5 次
  avatar-web-template       : 3 次
  ...
```

### 9.5 数据清理

#### 客户端本地库

```bash
# 重置（清空所有数据）
python ~/.claude/skills/iflytek-digital-human/tools/init_db.py --reset

# 删除已上传的旧数据（手动，未实现自动清理）
sqlite3 ~/.claude/iflytek-digital-human/telemetry/telemetry.db \
  "DELETE FROM workflows WHERE uploaded=1 AND started_at < datetime('now', '-7 days')"
```

#### 服务端数据库

根据 `retention_days` 定期清理（需要实现定时任务）：
```sql
DELETE FROM avatar_telemetry_invocation
WHERE workflow_id IN (
  SELECT workflow_id FROM avatar_telemetry_workflow
  WHERE started_at < DATE_SUB(NOW(), INTERVAL 90 DAY)
);

DELETE FROM avatar_telemetry_workflow
WHERE started_at < DATE_SUB(NOW(), INTERVAL 90 DAY);
```

### 9.6 安全与合规

#### 当前状态

**无鉴权** — `/zs_admin/avatarTelemetry/report` 完全开放，任何人知道地址就能灌数据。

admin 模块没有鉴权拦截器（只有 `HttpTraceFilter`），现有 admin 接口也是这个状态。如果只部署在内网、靠网关或防火墙隔离，这是可接受的。

**如果暴露公网，建议加共享密钥**：

```java
// AvatarTelemetryController.report() 开头
String token = request.getHeader("X-Telemetry-Token");
if (!telemetryToken.equals(token)) {
    return ResponseMsg.errResponse("Unauthorized");
}
```

客户端配置：
```json
{
  "endpoint": "https://...",
  "auth_token": "your-secret-here"
}
```

#### 合规告知门禁

用户同意流程在 `avatar-workflow-entry`，声明模板位于 `config/privacy_notice.json`。没有同意
记录时返回 `undecided`；声明版本或内容摘要发生变化时返回 `stale`，两种状态都会由入口展示
声明并要求用户明确选择。

客户端把同意绑定到声明内容摘要和地址。声明变化、旧 `notice_version`、拒绝或撤回都会让
Hook 和上传器立即停用。上报请求带 `privacyNoticeVersion` 与 `consentedAt`，服务端拒绝缺失、
过期或无效的授权信息。

#### 数据脱敏

- `anonymous_id` — SHA-256 截断，无法反推
- `xfyun_user_id` — SHA-256 截断，无法反推
- `workflow_id` — 初始值包含首次会话的 session_id，但那是 Claude Code 内部标识，不是用户真实信息
- `completion_detail` — 可能包含本地路径，但截断到 1000 字符，且只统计 clean_workflows

**未脱敏的**：
- `os` / `plugin_version` — 设备指纹维度，与 `anonymous_id` 结合可能加强追踪能力
- `skill_name` — 功能使用偏好

如果要达到 GDPR 匿名标准（单凭数据集无法识别个人），需要进一步泛化 `os`（win32 → windows）、去掉 `plugin_version`。
