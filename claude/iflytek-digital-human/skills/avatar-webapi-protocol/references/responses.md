# responses.md — 响应报文解读与会话状态判断

> 面向"用 WebAPI 直连讯飞虚拟人、需要解析 JSON 响应报文、判断会话状态"的开发者。
> 本文是解读响应 / 判断状态的权威参考。请求报文如何构造见 `protocols.md`。

服务端所有下行消息都是一条 JSON。判断逻辑的核心链路是：
**先看 `header.code` 是否为 0 → 再看 `payload` 落在哪个子对象(avatar/nlp/asr) → 对 avatar 子对象看 `event_type` → 按 event_type 取关键字段判断状态。**

---

## 1. 响应公共结构

响应报文分两层：`header` + `payload`。

```json
{
  "header": {
    "code": 0,
    "message": "success",
    "sid": "vdh00015952@hu19f40bc77520441882",
    "session": "",
    "status": 1
  },
  "payload": {
    "avatar": {
      "request_id": "9ff1986c-b006-4644-9cbe-5fb60136bf35",
      "event_type": "driver_status",
      "period": "driver",
      "error_code": 0,
      "error_message": ""
    }
  }
}
```

### 1.1 header 层

| 字段 | 含义 | 类型 | 判断用途 |
| :--- | :--- | :--- | :--- |
| code | 返回码，0=成功，非0=异常 | int | **第一道判断**：非0直接按错误处理，看 message |
| message | 错误描述，成功时为 `success` | string | code≠0 时读此字段 |
| sid | 本次 WebSocket 会话的 id | string | 全程不变，用于日志定位；reconnect 后会换新 sid |
| session | 会话信息，通常为空字符串 | string | 一般无需关注 |
| status | **整个 WebSocket 会话的生命周期阶段** | int | 见下表 |

**header.status —— 会话生命周期(注意：是整条连接的状态，不是单次驱动的状态)**

| status | 含义 | 什么时候出现 |
| :---: | :--- | :--- |
| 0 | 建立 | 连接刚建立阶段 |
| 1 | 进行中 | 绝大多数响应都是 1（start 成功后到 stop 之前） |
| 2 | 结束 | **只在 stop 响应里出现**，收到 status=2 表示会话已终止，应关闭 WebSocket |

> 注意区分：`header.status`(整条会话)与 `payload.avatar.vmr_status`(单次驱动进度)、
> `payload.nlp/asr.status`(单次流式分帧)是**三个不同层级的 status**，判断时别混。

### 1.2 payload 层 —— 三种子对象

`payload` 下只会出现以下三者之一，先判断是哪种再取字段：

| 子对象 | 出现在 | 判断内容 | 关键字段 |
| :--- | :--- | :--- | :--- |
| `payload.avatar` | 所有协议 | 推流/驱动/动作/审核等事件，靠 `event_type` 分流 | event_type / period / vmr_status / error_code |
| `payload.nlp` | 文本交互 / 音频交互 | 大模型语义理解结果（流式） | answer.text / ttsAnswer.text / status |
| `payload.asr` | 音频交互 | 语音识别结果（流式） | text / status |

`payload.avatar` 的公共字段：

| 字段 | 含义 | 类型 |
| :--- | :--- | :--- |
| request_id | 单次驱动/请求的 id（交互驱动会自动追加 `_0/_1/_2` 后缀，见 §3.6） | string |
| event_type | 事件类型，**解读响应的主分流字段**（见 §2） | string |
| period | 事件周期：`global`(会话级) / `driver`(单次驱动级) | string |
| error_code | 单次驱动/请求的异常码，0=成功，非0=异常 | int |
| error_message | 单次驱动/请求的异常描述 | string |
| cid | 虚拟人客户端实例 ID（avatar 侧 `vms` 前缀 / asr 侧 `iat` 前缀 / nlp 侧 `cht` 前缀） | string |

---

## 2. event_type 全表

以文档 §7.3 速查表为主干。**只有 `payload.avatar` 才带 event_type**；nlp/asr 子对象没有 event_type，靠自身 `status` 分帧。

| event_type | period | 出现协议 | 关键字段 | 含义 |
| :--- | :--- | :--- | :--- | :--- |
| `stream_info` | global | start（前置） | stream_url / stream_extend / cid | 推流信息，返回拉流地址与鉴权 token（拉流播放器用） |
| `stream_start` | global | 所有驱动类协议 | frame_number / cid | 推流正式开始 |
| `driver_status` | driver | text_driver / audio_driver / audio_interact / cmd | vmr_status / frame_number / rtp_timestamp / cid | 驱动状态（口型/音频/动作时序），**判断播报进度的核心事件** |
| `audit_result` | driver | text_driver / cmd | result.result.suggest(pass/reject) / result.result.detail | 内容安全审核结果 **[标准虚拟人专有，超拟人无此事件]** |
| `action_status` | driver | text_driver / audio_driver / cmd（需开关） | name / action_status(0触发/2完成) / frame_number / rtp_timestamp | 引擎动作处理状态，需 start 传 `avatar_dispatch.enable_action_status=1` 才回报 |
| `tts_duration` | driver | text_driver / audio_interact | tts_duration(毫秒) / request_id | 本次播报的 TTS 音频时长 |
| `subtitle_info` | driver | text_driver | bg / ed / text / request_id | 字幕信息（主要用于透明通道自绘字幕） |
| `cmd` | global | cmd | request_id / cid | 动作指令确认（cmd 协议专有的指令下发回执） |
| `reset` | global（reset 协议）/ global（音频交互自动） | reset / audio_interact(自动) | request_id / cid | 打断/重置确认。音频交互中服务端在 ASR/NLP 切换时会**自动**下发 reset 打断上一轮 |
| `pong` | global | 所有协议（心跳） | request_id（**无 cid**） | 心跳响应（对 ping 的回执） |
| `stop` | global | 所有协议（收尾） | request_id / cid | 停止会话确认，此响应 `header.status=2` |
| `reconnect` | driver | reconnect | request_id / cid | 断连重连确认（产生新 sid，旧 sid 失效） |
| `offline_url` | —（离线专用） | 离线模式（protocol=local） | 离线视频地址 | 离线视频生成完成，需 `single_interaction=true` |

**period 速记**：`global` = 会话级事件（推流、指令确认、心跳、停止、重置）；`driver` = 单次驱动生命周期内的事件（驱动状态、审核、动作、TTS 时长、字幕）。

> 补充坑点（来自 cmd 协议 §5.7 实测）：cmd 协议里 `driver_status` 的 `vmr_status` 实测为 `1`（进行中），且 request_id 可能是 `__local_0` 这类本地占位值；不要用它当作播报开始/结束判断，cmd 的完成以 `action_status=2` 为准。

---

## 3. 状态判断逻辑（本文重点）

### 3.1 start 是否成功

**正确判断**：连接建立后发 `start`，收到 —
1. `event_type = stream_info`（带 `stream_url` 推流地址 + `stream_extend.appid` / `stream_extend.user_sign` 鉴权 token）
2. `event_type = stream_start`（`frame_number` 起始帧，推流正式开始）

同时 `header.code = 0` 且 `payload.avatar.error_code = 0`。拿到 `stream_info.stream_url` 即可去拉流播放。

```json
{
  "header": { "code": 0, "message": "success", "sid": "vdh00015528@...", "status": 1 },
  "payload": { "avatar": {
    "request_id": "8271e778-65f9-4e7d-b7a6-d7599f5b33a9",
    "period": "global",
    "event_type": "stream_start",
    "error_code": 0, "error_message": "",
    "frame_number": 0,
    "cid": "vms000e662f@..."
  }}
}
```

> ⚠️ **文档校正（幽灵事件 avatar_ready）**：文档 §4.3 称 start 成功标志是
> `header.event_type = "avatar_ready"`。**实际不存在 `avatar_ready` 这个事件**，
> event_type 也不在 header 里而在 `payload.avatar` 里。
> **以 `stream_info` / `stream_start` 为准判断 start 成功**，切勿等待 `avatar_ready`（会永远等不到）。

### 3.2 播报是否结束

**判断依据**：`driver_status` 事件的 `vmr_status`。

| vmr_status | 含义 |
| :---: | :--- |
| 0 | 驱动开始（开始推流本次播报） |
| 1 | 中间处理 |
| 2 | 驱动结束（本段播报推流结束） |

**结束的严谨判断（§6.1 Q8）**：流式文本会多次循环 0→…→2，但一定以 0 开始、2 结束。
**当 `vmr_status=2` 且后续 1 秒内没有新的 `vmr_status=0`，才视为整段说话真正结束**，此时才可以发下一条驱动。

```json
{
  "payload": { "avatar": {
    "event_type": "driver_status",
    "vmr_status": 2,
    "frame_number": 62,
    "request_id": "9ff1986c-...", "error_code": 0
  }},
  "header": { "code": 0, "status": 1 }
}
```

> ⚠️ **文档校正（幽灵事件 avatar_end）**：文档 §4.4 / §6.2 称"收到 `avatar_end` 才能发下一次驱动"。
> **`avatar_end` 同样是不存在的幽灵事件**。实际判断播报结束只能靠 `vmr_status=2`（且 1 秒内无新的 0），
> 不要监听 `avatar_end`。

### 3.3 动作状态

只有 start 时传了 `avatar_dispatch.enable_action_status = 1`，服务端才会回报 `action_status` 事件。

| action_status | 含义 |
| :---: | :--- |
| 0 | 动作触发/开始 |
| 2 | 动作完成/结束 |

同一动作按生命周期分阶段回报多条，`name` 字段是动作名（如 `A_H_shake_O`）。cmd 协议做单独动作时，动作完成以 `action_status=2` 为准。

```json
{
  "payload": { "avatar": {
    "event_type": "action_status",
    "name": "A_H_shake_O",
    "action_status": 2,
    "frame_number": 71, "rtp_timestamp": 0,
    "error_code": 0
  }},
  "header": { "code": 0, "status": 1 }
}
```

### 3.4 审核结果

`audit_result` 事件携带内容安全审核结论。**仅标准虚拟人有此事件，超拟人不返回 audit_result**（其余事件两者一致）。

- `result.result.suggest`：审核结论，只有 `pass`（通过）/ `reject`（拒绝）两值。
- `reject` 时应视为内容被拦截，虚拟人不会播报该内容。
- `result.result.detail.content`：原始待审核文本（cmd 协议里是 JSON 字符串编码的指令）。

```json
{
  "payload": { "avatar": {
    "result": { "result": {
        "safe_classification": "",
        "suggest": "pass",
        "detail": { "content": "你好，这是文本驱动测试" }
      },
      "request_id": "T2026070815580111ccb0bdd2bf0f000"
    },
    "period": "driver",
    "event_type": "audit_result",
    "error_code": 0,
    "request_id": "9ff1986c-..."
  }},
  "header": { "code": 0, "status": 1 }
}
```

### 3.5 nlp 响应（语义理解，流式）

出现在文本交互 / 音频交互。位于 `payload.nlp`，**无 event_type**，靠自身 `status` 分帧。

| 字段 | 含义 |
| :--- | :--- |
| `answer.text` | 理解后的文本，**返回给客户端展示** |
| `ttsAnswer.text` | **实际驱动虚拟人播报**的文本（变声场景下可能与 answer 不同） |
| `text` | 送入理解的原始文本 |
| `service` | 语义服务名（如 `xinghuo`） |
| `status` | 流式状态：**0=首帧 / 1=中间 / 2=尾帧** |
| `index` | 分片序号 |
| `stream_nlp` | 是否流式输出（bool） |
| `error_code` | 异常码，0=成功 |
| `cid` | nlp 侧实例 ID，`cht` 前缀 |

**判断要点**：`answer.text`（给前端看）与 `ttsAnswer.text`（驱动播报）是两个用途；`status=2` 的尾帧里 `answer.text`/`ttsAnswer.text` 通常为空，表示流式结束。逐字拼接播报时应按标点拼成整段再驱动（§6.1 Q9），避免逐字调用卡顿。

```json
{
  "payload": { "nlp": {
    "request_id": "aae11c38-...",
    "text": "今天天气怎么样？",
    "service": "xinghuo",
    "status": 0,
    "error_code": 0,
    "answer": { "text": "请问您想查询哪个城市的天气？" },
    "ttsAnswer": { "text": "请问您想查询哪个城市的天气？" },
    "index": 0, "stream_nlp": true,
    "cid": "cht000df53a@..."
  }},
  "header": { "code": 0, "status": 1 }
}
```

### 3.6 asr 响应（语音识别，流式）

仅出现在音频交互。位于 `payload.asr`，**无 event_type**，靠自身 `status` 分帧。

| 字段 | 含义 |
| :--- | :--- |
| `text` | 语音识别出的文本 |
| `status` | 流式状态：**0=首帧 / 1=中间 / 2=尾帧** |
| `service` | 识别服务名（如 `iat-ws`） |
| `error_code` | 异常码，0=成功 |
| `role` / `lg` | 角色 / 语言标识，通常为空 |
| `cid` | asr 侧实例 ID，`iat` 前缀 |

`status=2` 的尾帧即本句识别的最终结果。

```json
{
  "payload": { "asr": {
    "request_id": "92dc0c23-...",
    "service": "iat-ws",
    "status": 2,
    "text": "嗯",
    "error_code": 0,
    "cid": "iat000d8437@...", "role": "", "lg": ""
  }},
  "header": { "code": 0, "status": 1 }
}
```

### 3.7 交互类 request_id 的 `_0/_1/_2` 后缀

在文本交互 / 音频交互中，一次交互往往触发多轮驱动（大模型分段回答，每段一次驱动）。
服务端会在原始 `request_id` 后**自动追加 `_0`、`_1`、`_2`……** 区分是第几轮驱动。

例：请求 request_id 为 `aae11c38-...`，驱动事件里会看到 `aae11c38-..._0`（第 1 轮）、`aae11c38-..._1`（第 2 轮）。判断"某一轮播报结束"时，要按**带后缀的 request_id** 去匹配对应的 `vmr_status=2`。

---

## 4. 错误判断

有两级错误码，都要检查：

| 层级 | 字段 | 含义 |
| :--- | :--- | :--- |
| 连接/会话级 | `header.code` | ≠0 表示会话级异常，看 `header.message` |
| 单次驱动/请求级 | `payload.avatar.error_code`（或 `nlp/asr.error_code`） | ≠0 表示本次驱动/请求异常，看 `error_message` |

**判断规则**：`header.code ≠ 0` **或** `payload` 里的 `error_code ≠ 0`，即为异常，读对应的 `message` / `error_message` 定位原因。二者都为 0 才算本条响应正常。

> 错误码含义速查：文档 §7.1 指向外部错误码表（链接见官方文档）。本 skill 内的错误码定位与
> 常见错误号对照见 `avatar-troubleshoot` 技能或平台错误码文档。这里不重复罗列错误码表。

---

## 5. 典型文本驱动一次完整响应序列（逐条解读）

以标准虚拟人一次 `text_driver` 播报"你好，这是文本驱动测试"为例，服务端依次下发：

**① audit_result** — `period=driver`, `event_type=audit_result`
```json
{ "payload": { "avatar": {
    "result": { "result": { "suggest": "pass", "detail": { "content": "你好，这是文本驱动测试" } } },
    "event_type": "audit_result", "error_code": 0, "request_id": "9ff1986c-..." }},
  "header": { "code": 0, "status": 1 } }
```
→ 读到 `suggest=pass`：文本通过内容安全审核，将会被播报。若是 `reject` 则本条不会播报，应提示被拦截。（超拟人跳过此步，无此事件）

**② tts_duration** — `event_type=tts_duration`
```json
{ "payload": { "avatar": {
    "event_type": "tts_duration", "tts_duration": 2546,
    "error_code": 0, "request_id": "9ff1986c-..." }},
  "header": { "code": 0, "status": 1 } }
```
→ TTS 合成完成，本段音频时长约 2546ms。可用于前端进度条/超时兜底估算，不代表已开始播报。

**③ stream_start** — `period=global`, `event_type=stream_start`
```json
{ "payload": { "avatar": {
    "event_type": "stream_start", "frame_number": 0,
    "error_code": 0, "request_id": "8bfc4c51-..." }},
  "header": { "code": 0, "status": 1 } }
```
→ 推流正式开始（从第 0 帧）。此时视频流开始输出。

**④ driver_status (vmr_status=0)** — 驱动开始
```json
{ "payload": { "avatar": {
    "event_type": "driver_status", "vmr_status": 0,
    "frame_number": 0, "rtp_timestamp": 0,
    "error_code": 0, "request_id": "9ff1986c-..." }},
  "header": { "code": 0, "status": 1 } }
```
→ 虚拟人**开始说话**。此刻标记"正在播报中"，不要发下一条驱动。

**⑤ driver_status (vmr_status=2)** — 驱动结束
```json
{ "payload": { "avatar": {
    "event_type": "driver_status", "vmr_status": 2,
    "frame_number": 62, "rtp_timestamp": 0,
    "error_code": 0, "request_id": "9ff1986c-..." }},
  "header": { "code": 0, "status": 1 } }
```
→ 本段播报推流结束。**再等 1 秒**确认无新的 `vmr_status=0`（流式文本可能再来一轮），确认后才判定"整段说话结束"，此时可安全发送下一条驱动或 `stop`。

**判断口诀**：审核(pass?) → 时长(估算) → 推流开始 → vmr=0(说话中) → vmr=2 且 1 秒内无新 vmr=0(说完了)。全程 `header.code=0` 且各条 `error_code=0` 才算正常。

---

> 请求报文构造见 `protocols.md`。
