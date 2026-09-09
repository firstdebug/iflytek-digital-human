---
name: audio-driver
description: 音频驱动功能实现指南（用音频数据直接驱动虚拟人口型和播报）
tags:
  - feature
  - audio-driver
  - tts
  - pcm
---

# avatar-audio-driver: 音频驱动

## 功能说明

直接向虚拟人推送音频数据（PCM/自有 TTS 合成的音频），虚拟人根据音频驱动口型并播放。适用于已有自研 TTS、需要特定音色、离线音频播报等场景。

**与文本驱动的区别**:
- **文本驱动**: 输入文本，平台 TTS 合成音频，虚拟人播报
- **音频驱动**: 输入已合成好的音频数据，虚拟人直接播报并驱动口型

## 触发条件 / 调用时机

- 已有自研 TTS 引擎，需要用自己合成的音频驱动虚拟人
- 需要特定音色、离线音频播报、播放预录音频
- 需要将实时音频流（如直播）转为虚拟人播报

## 核心工作流概览

1. 准备音频数据（必须为 16kHz / 16bit / 单声道 PCM，否则先转码）
2. 分帧，标记帧状态（首帧 0 / 中间帧 1 / 尾帧 2）
3. 通过 `writeAudio` 逐帧推送到虚拟人
4. 音频结束时务必推送尾帧（status=2）

| 步骤 | 接口 / 动作 | 关键点 |
|------|-------------|--------|
| 音频准备 | 自研 TTS / 转码 | 16kHz 16bit 单声道 PCM |
| 分帧 | 按 1280 字节(40ms) 切分 | 标记 frameStatus |
| 推送 | `writeAudio(data, status, opts)` | 首帧0/中间1/尾帧2 |
| 结束 | 推送空数据 + status=2 | 缺失会导致播报不结束 |

## 音频格式要求（HARD-GATE）

音频必须为 **16kHz 采样率、16bit、单声道 PCM** 格式：

```yaml
采样率: 16000 Hz (16kHz)
位深: 16 bit
声道: 单声道 (mono)
编码: PCM (无压缩)
字节序: 小端 (little-endian)
帧大小: 建议每帧 1280 字节 (40ms) 或 640 字节 (20ms)
```

**⚠️ 格式不匹配会导致口型不同步或无声音。** 若源音频不是 16kHz PCM，必须先转码，转码示例见 references/audio-transcoding.md。

## 决策分支（场景 → 应读哪个 reference）

| 场景 | 参考文件 |
|------|----------|
| 各平台（Web/Android/iOS）如何调用 `writeAudio` | references/platform-quickstart.md |
| 源音频不是 16kHz PCM，需要转码 | references/audio-transcoding.md |
| 流式（边合成边推送）或整段推送的实现 | references/push-strategies.md |
| 接入自研 TTS / 播放预录音频 / 实时音频流 | references/use-cases.md |
| 口型不同步、无声音、卡顿、播报不结束 | references/troubleshooting.md |

- 平台接入代码详见 references/platform-quickstart.md
- 音频转码详见 references/audio-transcoding.md
- 分帧推送策略详见 references/push-strategies.md
- 完整应用场景示例详见 references/use-cases.md
- 排障流程详见 references/troubleshooting.md

## 关键约束 / Red Flags

- **HARD-GATE**: 音频必须为 16kHz / 16bit / 单声道 PCM，非此格式先转码
- **必须推送尾帧**: 音频结束时务必推送 status=2 的尾帧，否则播报不结束
- **帧状态顺序**: 首帧 0 → 中间帧 1（可多次）→ 尾帧 2
- **Web 自动播放限制**: 需处理 `playNotAllowed`，引导用户点击后 `resume()`
- **推送节奏**: 帧过大或推送过快会卡顿，建议 1280 字节/帧（40ms）

## references/ 索引

| 文件 | 内容 |
|------|------|
| references/platform-quickstart.md | Web / Android / iOS 三端 `writeAudio` 分帧推送调用代码 |
| references/audio-transcoding.md | 重采样到 16kHz、Float32 转 PCM16 代码 |
| references/push-strategies.md | 流式推送、整段推送两种策略的完整实现 |
| references/use-cases.md | 自研 TTS 接入、播放预录音频、实时音频流三个场景示例 |
| references/troubleshooting.md | 口型不同步/无声音/卡顿/播报不结束的排查与解决 |

## 配置 / 验证清单

- [ ] 确认音频为 16kHz / 16bit / 单声道 PCM
- [ ] 正确设置帧状态（首帧0 / 中间帧1 / 尾帧2）
- [ ] 处理浏览器自动播放限制（Web）
- [ ] 音频结束推送尾帧
- [ ] 非 16kHz 音频先转码

## 相关技能

- `text-driver`: 文本驱动（平台 TTS）
- `voice-interact`: 语音交互（含音频上传）
- `avatar-troubleshoot`: 音频问题排查
