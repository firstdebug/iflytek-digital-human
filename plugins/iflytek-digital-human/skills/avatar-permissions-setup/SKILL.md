---
name: avatar-permissions-setup
description: 虚拟人录音和相机权限配置指南
---

# avatar-permissions-setup: 权限配置

## 定位

处理虚拟人语音交互所需的运行时权限配置和申请流程。

## 调用时机

- 由 `avatar-workflow-entry` 路由（权限问题）
- 由 `avatar-troubleshoot` 诊断出权限缺失
- 录音功能启动失败（错误码 20003）

---

## 核心工作流概览

1. 判定运行平台（Web / Android / iOS）
2. 检查静态权限声明（Manifest / Info.plist / 浏览器环境）
3. 在用户触发功能时申请运行时权限
4. 处理授予、拒绝、"不再询问"三种结果
5. 拒绝时提供降级方案或引导到系统设置

| 平台 | 核心要求 | 麦克风申请方式 |
|------|----------|----------------|
| Web | HTTPS 或 localhost 环境 | `navigator.mediaDevices.getUserMedia({ audio: true })` |
| Android | Manifest 声明 + 运行时申请 | `ActivityCompat.requestPermissions` (RECORD_AUDIO) |
| iOS | Info.plist 说明文案 + 运行时申请 | `AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio` |

---

## 决策分支（场景 → 应读哪个 reference）

- **Web 平台配置 / 检查 / HTTPS 环境问题** → 详见 `references/web-implementation.md`
- **Android 静态声明 + 运行时申请 + 崩溃排查** → 详见 `references/android-implementation.md`
- **iOS Info.plist + AVAudioSession + 权限申请** → 详见 `references/ios-implementation.md`
- **申请时机 / 文案 / 拒绝降级 / 输出格式** → 详见 `references/best-practices.md`

---

## 关键约束 / HARD-GATE

- **权限修改门禁（新增能力时必须先问）**：如果任务是**新增**语音/录音/摄像头能力，必须先取得
  用户对该能力的明确确认（含交互形态：按住说话 / 点击开始停止 / 自动 VAD / 全双工）。没有确认时
  **不得**添加 `RECORD_AUDIO`、麦克风说明文案、摄像头权限或运行时申请代码。
  用 `平台交互提问` 提问，规则见 `../avatar-shared/delivery-modes.md`。
  若任务是**排查已有权限错误**（如错误码 20003、Manifest 已声明但运行时崩溃），可以直接修复缺失
  声明和运行时申请，不需要额外确认。
- **Web 录音必须 HTTPS 或 localhost**：HTTP 环境下 `getUserMedia` 不可用，这是硬性要求。
- **Android targetSdkVersion >= 23 必须处理运行时权限**：仅在 Manifest 声明不够，未运行时申请会崩溃。
- **iOS 必须配置 NSMicrophoneUsageDescription**：未配置说明文案会导致申请直接失败/崩溃。
- **权限申请时机**：只在用户触发相关功能时申请，不在应用启动时立即申请。

## Red Flags

- 应用启动即申请所有权限（用户不知道用途，易被拒绝）
- 权限说明文案模糊或缺失
- 权限被拒绝后没有降级方案，也没有引导到设置
- 用户选择"不再询问"后仍反复弹窗申请（应改为引导到设置）

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/web-implementation.md` | Web 权限要求、浏览器支持检查、HTTPS 检查、权限变化监听、"不安全"问题诊断 |
| `references/android-implementation.md` | AndroidManifest 声明、运行时申请完整实现、RECORD_AUDIO 崩溃排查、"不再询问"处理 |
| `references/ios-implementation.md` | Info.plist 配置、AVAudioSession 配置、运行时申请、中断监听、录音无反应排查 |
| `references/best-practices.md` | 申请时机、权限说明文案、拒绝降级方案、诊断结果与修复方案输出格式 |

---

## 权限检查清单

### Web 平台
- [ ] 环境为 HTTPS 或 localhost
- [ ] navigator.mediaDevices 存在
- [ ] getUserMedia API 可用
- [ ] 用户已授予麦克风权限

### Android 平台
- [ ] AndroidManifest.xml 声明 RECORD_AUDIO
- [ ] targetSdkVersion >= 23 时已处理运行时权限
- [ ] 运行时权限申请流程完整
- [ ] 权限拒绝时有降级方案或引导
- [ ] 用户可在设置中找到权限开关

### iOS 平台
- [ ] Info.plist 配置 NSMicrophoneUsageDescription
- [ ] 运行时申请权限流程完整
- [ ] AVAudioSession 正确配置
- [ ] 权限拒绝时引导到设置
- [ ] 处理音频中断通知

---

## 相关技能

- `avatar-workflow-entry`: 路由入口
- `avatar-troubleshoot`: 调用本技能进行权限诊断
- `avatar-voice-interact`: 语音交互功能需要权限
