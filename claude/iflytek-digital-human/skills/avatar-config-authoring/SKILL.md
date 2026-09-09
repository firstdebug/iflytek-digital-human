---
name: avatar-config-authoring
description: >-
  虚拟人配置调整（分辨率/码率/帧率/形象/发音人/TTS
  参数/背景）。针对已集成的项目做主动的配置修改，区别于故障排查（avatar-troubleshoot）。
tags:
  - config
  - resolution
  - bitrate
  - avatar-resource
  - tts
priority: high
optional_tools:
  - name: query-services
    when: 需要确认可用的形象/发音人授权范围
    fallback: 参考 avatar-credentials 手动确认授权
  - name: query-scene-config
    when: 更换形象/发音人前需要读取场景当前配置
    fallback: 从项目 .env / 配置文件读取当前值
---

# avatar-config-authoring: 配置调整

## 定位

对**已集成虚拟人的项目**做主动的配置修改：分辨率、码率、帧率、形象、发音人、
播报速度、音量、背景等。与 `avatar-troubleshoot`（被动排障）区分——这里是用户
明确想"改成什么样"，而非"哪里出错了"。

**调用时机**:
- 由 `avatar-workflow-entry` 路由（信号：调整/修改、分辨率/码率/形象）
- 由 `avatar-brainstorming` 判定为"配置调整"意图后路由
- 用户主动要求调整已有配置

---

## 输入 / 输出契约

**输入**（来自路由）:
```yaml
config_type: "resolution" | "avatar_resource" | "tts_params" | "background" | "stream_params"
current_value: "720x1280"     # 可选，能读到就填
target_value: "1080x1920"
```

**输出**: 配置文件修改 + 影响说明（含风险/兼容性提示）。

---

## 核心工作流概览

| 阶段 | 目标 | 详见 |
|------|------|------|
| 1. 定位配置 | 找到项目中该配置项的位置（SDK 初始化 / .env / 场景配置） | 本页决策分支 |
| 2. 校验目标值 | 对照平台能力矩阵校验取值合法（避免 bitrate<200 等） | `references/config-params.md` |
| 3. 应用修改 | 修改代码/配置，保留原值备注 | `references/config-params.md` |
| 4. 影响说明 | 说明对性能/兼容/授权的影响 | `references/impact-matrix.md` |
| 5. 验证 | 交接 `avatar-verification` 确认修改生效且不破坏链路 | — |

---

## 决策分支（配置类型 → 位置 + 约束）

```
配置调整任务
├── resolution（分辨率）
│   ├── 位置: SDK 初始化的 width/height 参数
│   ├── 校验: 对照 platform-registry.yaml 各平台支持的分辨率
│   └── 影响: 越高越清晰但码率需相应提高，移动端注意性能
│
├── stream_params（码率/帧率）
│   ├── 位置: SDK 初始化 bitrate/framerate
│   ├── 校验（HARD）: bitrate ≥ 200，推荐 2000；framerate 常用 25
│   └── 影响: 见 avatar-troubleshoot 的 bitrate 坑（运行时案例）
│
├── avatar_resource（形象/发音人）
│   ├── 位置: avatarId / vcn（.env 或 SDK 参数）
│   ├── 校验（HARD）: 只能用【已授权】的 avatarId/vcn（否则报 10120）
│   │   └── 用 query-services 确认授权范围，或查 avatar-credentials
│   └── 影响: 超拟人（cnr 开头）不支持透明背景
│
├── tts_params（播报速度/音量/音调）
│   ├── 位置: 文本驱动/语音交互的 TTS 配置
│   └── 影响: 见 text-driver / voice-interact
│
└── background（背景）
    ├── 位置: 背景图/透明背景配置
    ├── 校验: 透明背景需 xrtc 协议且非超拟人形象
    └── 影响: 见 transparent-bg
```

---

## 关键约束 / HARD-GATE / Red Flags

- **bitrate ≥ 200**（数字类型，推荐 2000）——最常见的配置错误，改码率务必校验。
- **形象/发音人必须已授权**——改 avatarId/vcn 前用 `query-services` 或 `avatar-credentials`
  确认授权，未授权连接报 10120。
- **超拟人（cnr 开头）不支持透明背景**——涉及背景配置时先确认形象类型。
- **分辨率/协议兼容**——透明背景需 xrtc 协议，对照 `platform-registry.yaml`。
- **改完必须验证**——任何配置修改都交接 `avatar-verification`，防止破坏首帧链路。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/config-params.md` | 各配置项的合法取值范围、平台差异、修改位置与代码示例 |
| `references/impact-matrix.md` | 配置项 → 性能/兼容/授权影响对照表 |

> 平台能力矩阵（各平台支持的分辨率/协议/形象）以 `config/platform-registry.yaml` 为准。

---

## 验证清单 / 交接协议

- [ ] 目标值已对照平台能力矩阵校验合法
- [ ] 形象/发音人变更已确认授权
- [ ] 配置已修改且原值有备注
- [ ] 已向用户说明影响（性能/兼容/授权）

交接:
- 修改完成 → `avatar-verification`（确认生效且链路正常）
- 修改中发现是故障而非调整需求 → `avatar-troubleshoot`

---

## 相关技能

- `avatar-workflow-entry`: 路由入口
- `avatar-brainstorming`: 上游意图判定
- `avatar-verification`: 修改后验证
- `avatar-troubleshoot`: bitrate/SDK 等配置坑详解（运行时案例库）
- `avatar-credentials`: 形象/发音人授权确认
- `transparent-bg` / `text-driver` / `voice-interact`: 对应能力的配置细节
