# 讯飞虚拟人 WebAPI 请求报文参考（protocols.md）

面向"用 WebAPI（不用 SDK）直连讯飞虚拟人、手工构造 JSON 请求报文"的开发者。
本文件只覆盖 **请求侧**（发往服务端的报文）。响应侧解读见 responses.md，鉴权见 auth.md。

WebSocket 地址：`wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`（需在 URL 查询参数带鉴权，见 auth.md）。

---

## 0. 文档校正说明（原始文档自相矛盾，本文件按以下正确值编写）

原始接口文档存在若干笔误与畸形示例。以下为**已校正的权威结论**，构造报文时以本文件为准：

1. **ctrl 值：每个协议用各自独立的字符串**，即分别为
   `start` / `text_driver` / `text_interact` / `audio_driver` / `audio_interact` / `cmd` / `reset` / `ping` / `stop`。
   > 原文 §7.2「协议速查表」称文本驱动/文本交互/音频驱动/音频交互/cmd 的 ctrl 都 = `data`（并注"多个协议共用 ctrl=data"），**该说法错误，不要采用**。以正文 §5.2~§5.10 各协议 header 表内的独立值为准。

2. **stop 协议的 ctrl 是小写 `stop`。**
   > 原文 §5.10.3 请求参数表把 ctrl 限制写成大写 `Stop`，是笔误；请求示例 §5.10.2 用的是正确的小写 `stop`。

3. **音频交互（audio_interact）协议的 ctrl 是 `audio_interact`。**
   > 原文 §5.6.3 header 表把 ctrl 限制误写成 `audio_driver`，是复制粘贴笔误；请求示例 §5.6.2 用的是正确的 `audio_interact`。

4. **原文 JSON 示例中的畸形写法一律修正为合法 JSON。** 常见畸形：
   - `"audio_mode":1,0`（应为单一值，`0` 非实时 / `1` 实时，注释另写）
   - `"full_duplex":0,1`（应为单一值，`0` 关闭 / `1` 全双工）
   - start 示例中 `"height": 1920` 与其后 `"avatar_dispatch"` 之间缺逗号
   本文件所有模板均为**合法 JSON**；取值含义用 `//` 注释或表格说明，实际发送时请去掉注释（严格 JSON 不允许注释）。

5. **超拟人 vs 标准虚拟人（请求侧差异）**：两者所有协议的请求报文结构**完全相同**，唯一区别是超拟人的 `avatar_id` 需带 `cnr` 前缀（如 `cnrmkf0e2000000006`），且 start 需带 `avatar_type:"hyperreal"`、使用超拟人专用 `vcn`。响应侧差异（超拟人不返回 `audit_result`）见 responses.md。

---

## 1. 公共报文结构

所有请求报文由三层组成：`header` / `parameter` / `payload`。

```json
{
  "header": {
    "app_id": "应用ID",
    "request_id": "请求唯一ID（建议用UUID）",
    "ctrl": "控制字段，标识协议类型",
    "scene_id": "场景ID（仅 start 协议需要）"
  },
  "parameter": { },
  "payload": { }
}
```

| 分层 | 定位 | 规则 |
| :--- | :--- | :--- |
| header | 所有协议共有头部 | 固定核心字段，全协议必带 |
| parameter | 协议配置参数层 | 承载 avatar / tts / asr / air / avatar_dispatch 等业务配置 |
| payload | 业务数据负载层 | 承载 text / audio / cmd_text / background 等核心数据 |

### header 公共字段

| 字段 | 类型 | 取值/限制 | 必填 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | 平台申请的 App ID |
| request_id | string | maxLength 50 | 是 | 单次请求唯一 ID，建议 UUID |
| ctrl | string | 各协议独立值（见校正说明第1条） | 是 | 协议类型标识 |
| scene_id | string | maxLength 50 | **仅 start 必带** | 场景 ID；非 start 协议不需要 |

> 连接后第一个发送的协议必须是 start；一个会话只能发一次 start。之后驱动类协议可多次发送，但同一时刻只能有 1 个驱动在执行（等 `vmr_status=2` / `avatar_end` 后再发下一条，或用追加模式排队）。

---

## 2. start 启动协议

**ctrl = `start`**（唯一需要 `scene_id` 的协议）。作用：启动会话，配置虚拟人形象、音色、字幕、视频输出参数与背景。必须在连接后首个发送，一个会话仅一次。

### 请求模板（标准虚拟人）

```json
{
  "header": {
    "app_id": "xxxx",
    "request_id": "xxxx",
    "ctrl": "start",
    "scene_id": "xxxx"
  },
  "parameter": {
    "avatar": {
      "stream": {
        "protocol": "xrtc",
        "fps": 25,
        "bitrate": 2000,
        "alpha": 0
      },
      "mask_region": "[0,0,1080,1920]",
      "move_h": 0,
      "move_v": 0,
      "scale": 1.0,
      "avatar_id": "111310001",
      "width": 1080,
      "height": 1920,
      "avatar_dispatch": { "enable_action_status": 1 }
    },
    "tts": {
      "vcn": "x4_lingxiaoqi_oral",
      "speed": 50,
      "pitch": 50,
      "volume": 50
    },
    "subtitle": {
      "subtitle": 1,
      "font_color": "#FFFFFF",
      "font_size": 10,
      "font_name": "mainTitle",
      "position_x": 0,
      "position_y": 0,
      "width": 100,
      "height": 100
    }
  },
  "payload": {
    "background": {
      "data": "res_key_或留空使用绿幕"
    }
  }
}
```
说明：`avatar_dispatch.enable_action_status=1` 表示需要引擎回报动作处理状态（`action_status` 事件），不需要可省略或填 0。`subtitle` 段仅在需要云端贴字幕时携带。

### 请求模板（超拟人）

与标准结构相同，差异：`avatar_id` 带 `cnr` 前缀、加 `avatar_type:"hyperreal"`、`vcn` 用超拟人专用声音。

```json
{
  "header": {
    "app_id": "xxxx",
    "request_id": "xxxx",
    "ctrl": "start",
    "scene_id": "xxxx"
  },
  "parameter": {
    "avatar": {
      "stream": { "protocol": "webrtc", "fps": 25, "bitrate": 4000, "alpha": 0 },
      "avatar_id": "cnrmkf0e2000000006",
      "width": 1920,
      "height": 1080,
      "avatar_type": "hyperreal"
    },
    "tts": { "vcn": "超拟人专用声音ID", "speed": 50, "pitch": 50, "volume": 50 }
  }
}
```

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `start` | 是 | - |
| request_id | string | maxLength 50 | 是 | - |
| scene_id | string | maxLength 50 | 否（但 start 通常必配） | - |

### parameter.avatar 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| stream | Object | 推流数据段 | 是 | - |
| stream.protocol | string | `rtmp` / `xrtc` / `webrtc` / `flv` | 是 | rtmp |
| stream.fps | int | 13-25 | 否 | 25 |
| stream.bitrate | int | 200-20000（单位 kb） | 否 | 2000 |
| stream.alpha | int | `1` 透明通道（仅 protocol=xrtc 生效） | 否 | 0 |
| avatar_id | string | 平台授权的形象 id（超拟人带 cnr 前缀） | 是 | 授权形象 id |
| avatar_type | string | 超拟人填 `hyperreal`；标准可不填 | 否 | - |
| mask_region | string | `[左,上,右,下]` 如 `[0,0,1080,1920]` | 否 | 形象裁剪参数 |
| width | int | 4 的倍数，[300,4096] | 否 | 720 |
| height | int | 4 的倍数，[300,4096] | 否 | 1280 |
| scale | float | [0.1, 1.0] 主播在背景中大小 | 否 | 1.0 |
| move_h | int | [-4096,+4096] 负=左移 正=右移 | 否 | 0 |
| move_v | int | [-4096,+4096] 负=下移 正=上移 | 否 | 0 |
| audio_format | int | `1`=16k / `2`=24k 音频驱动采样率 | 否 | 1 |
| avatar_dispatch.enable_action_status | int | `1` 需要动作状态回报 / `0` 不需要 | 否 | 0 |

### parameter.tts 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| vcn | string | 平台授权的声音 id | 否 | 授权声音 id |
| speed | int | [0,100] | 否 | 50 |
| pitch | int | [0,100] | 否 | 50 |
| volume | int | [0,100] | 否 | 50 |

### parameter.subtitle 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| subtitle | int | `1` 云端贴字幕（`0` 不贴） | 否 | 0 |
| font_color | string | 十六进制颜色 | 否 | #FFFFFF |
| font_size | int | 1-10 | 否 | - |
| font_name | string | `Sanji.Suxian.Simple` / `Honglei.Runninghand.Sim` / `Hunyuan.Gothic.Bold` / `Huayuan.Gothic.Regular` / `mainTitle` | 否 | mainTitle |
| position_x | int | 0-10000（须配合 width） | 否 | 0 |
| position_y | int | 0-10000（须配合 height） | 否 | 0 |
| width | int | 字幕宽 | 否 | 0 |
| height | int | 字幕高 | 否 | 0 |

### payload.background 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| data | string | 平台下发的资源 res_key | 否 | 绿幕 |

---

## 3. text_driver 文本驱动协议

**ctrl = `text_driver`**。作用：将文本转语音并驱动虚拟人播报（不走语义理解）。适用固定话术、通知、欢迎语。需等上一条驱动完成（`vmr_status=2`）后再发下一条，或用追加模式排队。

### 请求模板

```json
{
  "header": {
    "app_id": "xxxx",
    "ctrl": "text_driver",
    "request_id": "yyyy"
  },
  "parameter": {
    "avatar_dispatch": {
      "interactive_mode": 1
    },
    "tts": {
      "vcn": "",
      "speed": 50,
      "pitch": 50,
      "volume": 50
    },
    "air": {
      "air": 0,
      "add_nonsemantic": 0
    }
  },
  "payload": {
    "text": {
      "content": "我是数字人"
    }
  }
}
```
`interactive_mode`：`0` 追加（排队，等当前播报完再播下一条）/ `1` 打断（新内容自动打断当前播报）。`tts`、`air` 均可省略（用形象默认配置）。

### 动作标签（可选，嵌在 content 中）

在 `content` 文本内插入动作标签，虚拟人播报到该位置时执行对应动作（形象需支持动作）：

```json
{
  "payload": {
    "text": {
      "content": "大家好[action_wave]，欢迎来到直播间[action_thumbup]"
    }
  }
}
```

| 动作标签 | 说明 |
| :--- | :--- |
| `[action_wave]` | 挥手 |
| `[action_nod]` | 点头 |
| `[action_heart]` | 比心 |
| `[action_thumbup]` | 点赞 |
| `[action_clap]` | 鼓掌 |

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `text_driver` | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

### parameter.avatar_dispatch 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| interactive_mode | int | `0` 追加 / `1` 打断 | 否 | 1（打断） |

### parameter.tts 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| vcn | string | 授权发音人（如 x4_yezi） | 否 | 形象默认发音人 |
| speed | int | [0,100] | 否 | 50 |
| pitch | int | [0,100] | 否 | 50 |
| volume | int | [0,100] | 否 | 50 |

### parameter.air 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| air | int | `0` 关闭 / `1` 开启自动动作（形象需支持动作） | 否 | 0 |
| add_nonsemantic | int | `0` 关闭 / `1` 开启无指向性动作 | 否 | 0 |

### payload.text 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| content | string | 驱动文本，≤2000 字符（可含动作标签） | 是 | - |

---

## 4. text_interact 文本交互协议

**ctrl = `text_interact`**。作用：文本经大模型语义理解后生成回复并驱动播报。需平台配置大模型（如讯飞星火）。适用智能客服、问答、多轮对话。

### 请求模板

```json
{
  "header": {
    "app_id": "",
    "ctrl": "text_interact",
    "request_id": ""
  },
  "parameter": {
    "tts": {
      "vcn": "",
      "speed": 50,
      "pitch": 50,
      "volume": 50
    },
    "air": {
      "air": 0,
      "add_nonsemantic": 0
    }
  },
  "payload": {
    "text": {
      "content": "你能做什么"
    }
  }
}
```
注：`tts.vcn` 此处优先级高于 start 中的 vcn（变声在 start 声音合成后再转为此 vcn，合成时长略长）。`air` 自动动作只有交互走到大模型时才生效；`add_nonsemantic` 需配合 nlp 生效。

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `text_interact` | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

### parameter.tts 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| vcn | string | 授权发音人（优先级高于 start） | 否 | 形象默认发音人 |
| speed | int | [0,100] | 否 | 50 |
| pitch | int | [0,100] | 否 | 50 |
| volume | int | [0,100] | 否 | 50 |

### parameter.air 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| air | int | `0` 关闭 / `1` 开启自动动作（走大模型时生效，形象需支持动作） | 否 | 0 |
| add_nonsemantic | int | `0` 关闭 / `1` 开启无指向性动作（需配合 nlp 生效） | 否 | 0 |

### payload.text 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| content | string | 走语义的文本，≤2000 字符 | 是 | - |

---

## 5. audio_driver 音频驱动协议

**ctrl = `audio_driver`**。作用：直接用音频驱动口型，不做语义理解，只做口唇匹配。音频要求 **PCM，16bit，16kHz，单声道**。音频数据分片发送，每片 base64 编码。

### 请求模板

```json
{
  "header": {
    "app_id": "",
    "ctrl": "audio_driver",
    "request_id": ""
  },
  "parameter": {
    "avatar_dispatch": {
      "audio_mode": 1
    }
  },
  "payload": {
    "audio": {
      "encoding": "raw",
      "sample_rate": 16000,
      "channels": 1,
      "bit_depth": 16,
      "status": 0,
      "seq": 1,
      "audio": "音频base64",
      "frame_size": 0
    }
  }
}
```
`audio_mode`：`0` 非实时（音频文件）/ `1` 实时音频。`status`：一段音频从 `0`（开始）经多个 `1`（过渡）到 `2`（结束），即 0-1-1-…-1-2。可选变声：在 parameter 加 `vc` 段（`vc:1` 开启、`voice_name` 为变声发音人）。

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `audio_driver` | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

### parameter.avatar_dispatch 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| audio_mode | int | `0` 非实时（音频文件）/ `1` 实时音频 | 否 | 0 |

### parameter.vc 字段约束（可选，音色转换）

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| vc | int | `0` 不开启 / `1` 开启 | 否 | 0 |
| voice_name | string | 变声发音人（同 vcn，需授权） | 否 | - |

### payload.audio 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| encoding | string | `raw` / `lame` / `opus-wb` / `speex-wb`（raw 即 PCM） | 否 | 可枚举 |
| sample_rate | int | 16000 / 24000 | 否 | 16000 |
| channels | int | 1（单声道） | 否 | 1 |
| bit_depth | int | 16 | 否 | 16 |
| status | int | `0` 开始 / `1` 中间过渡 / `2` 结束 | 是 | - |
| seq | int | 数据序号，0-9999999 | 否 | 0 |
| frame_size | int | 帧大小，0-1024 | 否 | 0 |
| audio | string | 音频 base64，1B-10485760B | 是 | - |

> 性能建议：音频驱动每片 ≤3.2KB（约 40ms 音频），发送频率约 40ms/次。

---

## 6. audio_interact 音频交互协议

**ctrl = `audio_interact`**（校正：原文 §5.6.3 误写为 audio_driver）。作用：语音识别（ASR）+ 语义理解（NLP）+ 驱动，适用语音对话 / 全双工。需平台配置 ASR 和大模型。音频要求同音频驱动：**PCM，16bit，16kHz，单声道**。

### 请求模板

```json
{
  "header": {
    "app_id": "",
    "ctrl": "audio_interact",
    "request_id": ""
  },
  "parameter": {
    "asr": {
      "full_duplex": 0
    }
  },
  "payload": {
    "audio": {
      "encoding": "raw",
      "sample_rate": 16000,
      "channels": 1,
      "bit_depth": 16,
      "status": 0,
      "seq": 1,
      "audio": "音频base64",
      "frame_size": 0
    }
  }
}
```
`full_duplex`：`0` 关闭 / `1` 全双工（边说边交互）。`status` 规则同音频驱动：0-1-…-1-2。同样可选 `vc` 变声段。

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `audio_interact`（**非 audio_driver**） | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

### parameter.asr 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| full_duplex | int | `0` 关闭 / `1` 全双工 | 否 | 0 |

### parameter.vc 字段约束（可选，音色转换）

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| vc | int | `0` 不开启 / `1` 开启 | 否 | 0 |
| voice_name | string | 变声发音人（同 vcn，需授权） | 否 | - |

### payload.audio 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| encoding | string | `raw` / `lame` / `opus-wb` / `speex-wb` | 否 | 可枚举 |
| sample_rate | int | 16000 / 24000 | 否 | 16000 |
| channels | int | 1（单声道） | 否 | 1 |
| bit_depth | int | 16 | 否 | 16 |
| status | int | `0` 开始 / `1` 中间过渡 / `2` 结束 | 是 | - |
| seq | int | 数据序号，0-9999999 | 否 | 0 |
| frame_size | int | 帧大小，0-1024 | 否 | 0 |
| audio | string | 音频 base64，1B-10485760B | 是 | - |

---

## 7. cmd 单独指令协议

**ctrl = `cmd`**（校正：原文 §7.2 速查表误标为 data）。作用：发送独立动作指令，驱动虚拟人做特定动作（挥手、点头等）。动作需形象支持，动作名可在交互平台-接口服务-形象列表右侧「查看动作」获取。

### 请求模板

```json
{
  "header": {
    "app_id": "",
    "ctrl": "cmd",
    "request_id": ""
  },
  "payload": {
    "cmd_text": {
      "avatar": [
        {
          "type": "action",
          "value": "A_LH_introduced_O",
          "tb": 0
        }
      ]
    }
  }
}
```
`avatar` 是动作数组，可放多个动作对象。`tb=0` 表示立即触发。

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `cmd` | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

### payload.cmd_text 字段约束

| 字段 | 类型 | 取值范围 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| avatar | JsonArray | 虚拟人动作指令数组 | 是 | - |
| avatar[].type | string | `action`（动作） | 是 | - |
| avatar[].value | string | 动作名称（如 `A_LH_introduced_O`，形象需支持） | 是 | - |
| avatar[].tb | int | 时间偏移（相对子会话开始的毫秒数）；`0` 立即触发 | 是 | 0 |

> 若需引擎回报动作处理状态（`action_status` 事件），start 时须设置 `avatar_dispatch.enable_action_status=1`。

---

## 8. reset 重置协议

**ctrl = `reset`**。作用：打断虚拟人当前说话/动作，清空排队中的驱动，恢复静默推流。**仅需 header，无 parameter / payload。**

### 请求模板

```json
{
  "header": {
    "app_id": "",
    "ctrl": "reset",
    "request_id": "xxxx"
  }
}
```

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `reset` | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

---

## 9. ping 保活协议

**ctrl = `ping`**。作用：心跳保活，防止 WebSocket 超时断开。**仅需 header。** 推荐 30-60 秒发一次（60 秒内无任何消息服务端会断开；超 90 秒无响应视为断连）。

### 请求模板

```json
{
  "header": {
    "app_id": "",
    "ctrl": "ping",
    "request_id": ""
  }
}
```

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `ping` | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

---

## 10. stop 停止协议

**ctrl = `stop`**（校正：原文 §5.10.3 参数表误写为大写 `Stop`，正确为小写 `stop`）。作用：停止会话、释放服务端资源。**仅需 header。** stop 后应关闭 WebSocket 连接。

### 请求模板

```json
{
  "header": {
    "app_id": "xxxx",
    "ctrl": "stop",
    "request_id": "yyyy"
  }
}
```

### header 字段约束

| 字段 | 类型 | 取值/限制 | 必填 | 默认 |
| :--- | :--- | :--- | :--- | :--- |
| app_id | string | maxLength 50 | 是 | - |
| ctrl | string | 固定 `stop`（小写，**非 Stop**） | 是 | - |
| request_id | string | maxLength 50 | 是 | - |

---

## 附：ctrl 值速查（本文件校正后的权威取值）

| 协议 | ctrl | parameter 关键段 | payload 关键段 |
| :--- | :--- | :--- | :--- |
| start 启动 | `start` | avatar / tts / subtitle | background |
| 文本驱动 | `text_driver` | avatar_dispatch / tts / air | text |
| 文本交互 | `text_interact` | tts / air | text |
| 音频驱动 | `audio_driver` | avatar_dispatch / vc | audio |
| 音频交互 | `audio_interact` | asr / vc | audio |
| cmd 单独指令 | `cmd` | -（无） | cmd_text |
| reset 重置 | `reset` | -（仅 header） | -（仅 header） |
| ping 保活 | `ping` | -（仅 header） | -（仅 header） |
| stop 停止 | `stop` | -（仅 header） | -（仅 header） |

> 实际发送时请移除本文件模板中的 `//` 注释与 `scene_id` 之外的说明性文字，确保发送内容为严格合法 JSON。
>
> 响应侧解读见 responses.md，鉴权见 auth.md。
