> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。

# 短语音交互资料

短语音链路是“录音 -> ASR -> NLP -> 虚拟人回答”，适用于契约已经明确启用的语音问答。

## 契约门禁

开始写代码或改权限前必须先用契约校验器确认：

- `features.enabled` 包含 `voice_interact`；全双工任务则包含 `full_duplex`。
- `decisions.voice_interaction` 已记录用户在 Grill 阶段选择的交互形态。
- `permissions.microphone_confirmed=true`。

未满足时停止执行，把 `voice_interact`、`full_duplex` 和麦克风能力保留在 `features.excluded`，或回到 Grill 修改并重新确认契约。执行阶段不得现场追问是否顺便加入语音，也不得自行选择按住说话、点击开始/停止、VAD 或全双工。

## 实现资料

只读取契约平台对应的资料：

| 平台/问题 | 资料 |
|---|---|
| Web 权限、录音器、VAD 和 UI 形态 | `references/web-implementation.md` |
| Android 权限、录音器和事件 | `references/android-implementation.md` |
| iOS 权限、AVAudioSession 和事件 | `references/ios-implementation.md` |
| 权限拒绝、录音无响应和错误码 | `references/troubleshooting.md` |

## 已知约束

- 采样率 16000 Hz，PCM 16bit。
- Web 必须在 HTTPS 或 localhost 访问麦克风。
- 录音请求携带 `nlp: true` 才触发语义理解与回复。
- 短语音单次最长 60 秒。
- `stopRecord()` 必须发送尾帧，否则最后一段语音不会完成处理。
- 语音权限、录音代码和 UI 只实现契约已确认的交互形态。

## 验证

- 麦克风授权和拒绝路径均可观察。
- ASR/NLP 事件来自真实运行，不手写结果。
- 停止录音后最后一段语音得到处理。
- 未启用全双工时，不加入持续拾音、实时打断或回声处理。
