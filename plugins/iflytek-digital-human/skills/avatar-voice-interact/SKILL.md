---
name: avatar-voice-interact
description: 语音交互功能实现指南
---

# avatar-voice-interact: 语音交互

## 功能说明

用户通过语音提问，虚拟人识别后理解并回答，适用于语音客服、智能问答等场景。

**依赖能力**: ASR (语音识别) + NLP (语义理解)

---

## 调用时机

当需要实现「用户说话 → 虚拟人识别 → 理解并回答」的语音问答链路时使用本技能，包括语音客服、智能问答等场景。

---

## 用户确认门禁（HARD-GATE）

语音能力会新增麦克风权限、录音采集和运行时授权流程。**开始写代码或改权限前必须先用
`平台交互提问` 问用户确认**，同时确认交互方式：

| 选项 | 说明 |
|------|------|
| 按住说话 | 按下录音、松开结束，最简单可靠 |
| 点击开始/停止 | 点击切换录音状态，适合长问句 |
| 自动 VAD | 静音检测自动断句，无需手动操作 |
| 全双工实时对话 | 持续拾音 + 可打断，改用 `avatar-full-duplex` |

规则：

- 仅当用户在**当前任务**中明确确认后才继续。用户只说"加语音识别吧""顺便加语音"也要先问一次形态。
- 得到"确认 / 就按住说话 / 开始加"等明确答复后，才修改 AndroidManifest.xml、Info.plist、
  浏览器权限、录音代码或语音 UI。
- 用户未确认前**不得**加入 `RECORD_AUDIO`、不得申请麦克风权限、不得写录音代码或语音 UI。
- 用户只要求文本对话时，不得自行添加语音功能——改用 `avatar-text-interact`。
- 本门禁独立于交付模式门禁，即使 `workflow_mode` 已确定也要单独问语音。

完整门禁规则见 `../avatar-shared/delivery-modes.md`。

---

## 核心工作流概览

语音交互的通用流程：

1. 配置麦克风权限（各平台方式不同）
2. 创建录音器（采样率固定 16000）
3. 监听 ASR / NLP 事件
4. 开始录音（携带 `nlp: true`）
5. 停止录音（发送尾帧）

| 阶段 | 关键动作 | 说明 |
|------|----------|------|
| 权限 | 申请麦克风权限 | Web=HTTPS/localhost，Android=运行时权限，iOS=Info.plist |
| 初始化 | 创建录音器 | 采样率 16000，PCM 16bit |
| 监听 | 订阅 asr / nlp / vad 事件 | 获取识别结果与回复 |
| 录音 | startRecord + nlp:true | 短语音最长 60 秒 |
| 结束 | stopRecord | 发送尾帧完成一轮交互 |

---

## 决策分支（场景 → 应读哪个 reference）

| 场景 | 参考文件 |
|------|----------|
| Web 平台实现（权限、接入、全双工、VAD、UI 模式） | `references/web-implementation.md` |
| Android 平台实现（权限、接入） | `references/android-implementation.md` |
| iOS 平台实现（权限、接入） | `references/ios-implementation.md` |
| 排查权限、录音无反应、识别不准、错误码 | `references/troubleshooting.md` |

- Web 实现详见 `references/web-implementation.md`（含全双工模式、VAD 端点检测、按住说话/点击开始停止等 UI 模式）
- Android 实现详见 `references/android-implementation.md`
- iOS 实现详见 `references/ios-implementation.md`
- 遇到问题先查 `references/troubleshooting.md`

---

## 关键约束

- **采样率必须为 16000**，音频格式必须为 **PCM 16bit**，否则录音无反应。
- **Web 环境必须为 HTTPS 或 localhost**，否则无法访问麦克风。
- 录音时必须携带 `nlp: true` 才会触发语义理解与回复。
- 短语音单次录音最长 **60 秒**。
- 停止录音需调用 `stopRecord()` 发送尾帧，否则最后一段语音不会被处理。

### Red Flags

- 录音器启动失败（错误码 **20003**）：权限未配置/被拒绝、iOS AVAudioSession 配置错误、或麦克风被其他应用占用。参考 `avatar-permissions-setup`。
- 采样率不是 16000 或格式不是 PCM 16bit → 录音无反应。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/web-implementation.md` | Web 权限配置、快速接入、全双工模式、VAD 端点检测、按住说话/点击 UI 模式、权限被拒处理 |
| `references/android-implementation.md` | Android 运行时权限、录音器创建与事件监听、开始/停止录音 |
| `references/ios-implementation.md` | iOS Info.plist 配置、录音器创建与事件监听、开始/停止录音 |
| `references/troubleshooting.md` | 权限被拒、录音无反应、识别不准、错误码 20003 排查 |

---

## 验证清单

- [ ] 麦克风权限已按目标平台配置并通过申请
- [ ] 录音器采样率为 16000、格式为 PCM 16bit
- [ ] （Web）运行环境为 HTTPS 或 localhost
- [ ] 已监听 asr / nlp 事件并能收到结果
- [ ] 录音携带 `nlp: true`，可正常触发回复
- [ ] 停止录音后最后一段语音被正确处理

---

## 相关技能

- `avatar-text-driver`: 文本驱动
- `avatar-text-interact`: 文本交互
- `avatar-permissions-setup`: 权限配置
