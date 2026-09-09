# Phase 5: 生成设计文档

**目的**: 将访谈结果结构化为设计文档

## 5.1 设计文档结构

```markdown
# 虚拟人集成设计文档

## 1. 项目概述

### 1.1 工程信息
- 平台: Web / Android / iOS
- 项目路径: xxx
- 构建工具: xxx
- 语言: xxx

### 1.2 当前状态
- SDK 集成状态: 未集成 / 部分集成 / 完全集成
- 已有功能: xxx
- 缺失功能: xxx

## 2. 需求与目标

### 2.1 核心需求
(用户原始需求描述)

### 2.2 功能目标
- [ ] 文本驱动播报
- [ ] 文本交互（NLP）
- [ ] 语音交互
- [ ] 动作控制
- [ ] 透明背景
- [ ] 字幕显示

### 2.3 非功能需求
- 延迟要求: 低 / 中 / 高
- 网络环境: 稳定 / 弱网
- 设备兼容: xxx

## 3. 技术选型

### 3.1 SDK 版本
- Web: avatar-sdk-web_3.2.3.1002
- Android: avatar-core-v3.2.7 + xrtcsdk-5.2024.3.0
- iOS: AvatarSDK 3.2.1 + XRTCSDK

### 3.2 协议选择
- 视频流协议: XRTC / WebRTC / RTMP
- 选择理由: xxx

### 3.3 资源配置
- appId: xxx
- sceneId: xxx
- avatarId: xxx (形象类型: 标准 / 超拟人)
- vcn: xxx

## 4. 架构设计

### 4.1 模块划分
```
[用户界面层]
      ↓
[SDK 集成层] - AvatarPlatform / Controller / Player / Recorder
      ↓
[服务通信层] - WebSocket / XRTC
      ↓
[虚拟人服务]
```

### 4.2 关键流程

**初始化流程**:
1. 初始化 AvatarPlatform (凭据)
2. 创建播放器
3. 设置全局参数
4. 注册事件监听器
5. 启动虚拟人

**交互流程** (以语音交互为例):
1. 申请麦克风权限
2. 创建录音器
3. 开始录音
4. 上送音频帧
5. 停止录音（发送尾帧）
6. 接收 ASR 结果
7. 接收 NLP 回复
8. 虚拟人播报

## 5. 实现细节

### 5.1 权限处理

**Web**:
- HTTPS 或 localhost 环境
- navigator.mediaDevices.getUserMedia 权限
- 浏览器自动播放限制处理

**Android**:
- INTERNET (必需)
- RECORD_AUDIO (语音功能)
- 运行时权限申请

**iOS**:
- NSMicrophoneUsageDescription (Info.plist)
- AVAudioSession 配置
- 运行时权限引导

### 5.2 参数配置

```yaml
AvatarParams:
  stream:
    protocol: "xrtc"
    fps: 25
    bitrate: 2000
    alpha: 1  # 透明背景
  
  avatar:
    avatar_id: "xxx"
    width: 720
    height: 1280
    scale: 1.0
  
  tts:
    vcn: "xxx"
    speed: 50
    pitch: 50
    volume: 50
  
  scene:
    scene_id: "xxx"
  
  dispatch:
    interactive_mode: 0  # 0追加/1打断
```

### 5.3 事件处理

**必需监听**:
- connected: 连接成功
- stream_start: 推流开始
- frame_start / frame_end: 播报起止
- error: 错误处理

**可选监听**:
- asr: 语音识别结果
- nlp: 语义理解结果
- subtitle_info: 字幕信息
- action_start / action_stop: 动作起止

### 5.4 错误处理

**网络错误**:
- 10200 连接超时 → 检查网络和防火墙
- 10201 握手失败 → 检查服务地址

**鉴权错误**:
- 10110 appId 错误 → 检查拼写
- 10113 apiSecret 错误 → 检查签名生成

**资源错误**:
- 10120 avatarId 未授权 → 到控制台授权
- 10121 vcn 未授权 → 到控制台授权

## 6. 测试与验证

### 6.1 单元测试
- SDK 初始化
- 参数配置正确性
- 事件监听器注册

### 6.2 集成测试
- 完整初始化链路
- 文本驱动播报
- 语音交互（如需）
- 错误处理

### 6.3 兼容性测试
- 目标设备/浏览器
- 不同网络环境
- 权限拒绝场景

## 7. 部署与上线

### 7.1 环境要求
- Web: HTTPS 生产环境
- Android: 签名配置、混淆规则
- iOS: 证书、Bundle ID

### 7.2 上线检查
- [ ] 凭据配置（不包含明文 apiSecret）
- [ ] 权限申请流程完整
- [ ] 错误处理和用户提示
- [ ] 日志脱敏
- [ ] 性能和内存测试

## 8. 风险与注意事项

### 8.1 已知风险
- 浏览器自动播放限制（Web）
- 弱网环境首帧延迟
- 低端设备解码能力

### 8.2 规避措施
- 引导用户交互后播放
- 降低码率和分辨率
- 设备能力检测和降级

### 8.3 回退方案
- 播放失败时显示静态图
- 语音交互失败时回退到文本输入
- 透明背景不支持时使用普通背景

## 9. 文档与资源

### 9.1 相关文档
- [Web SDK 接入指南](https://doc.xfyun.cn/avatar/web-sdk)
- [Android SDK 接入指南](https://doc.xfyun.cn/avatar/android-sdk)
- [iOS SDK 接入指南](https://doc.xfyun.cn/avatar/ios-sdk)
- [错误码说明](https://doc.xfyun.cn/avatar/error-codes)

### 9.2 示例代码
- Demo 工程路径: xxx
- 参考示例: xxx

## 10. 变更记录
- 2026-07-13: 初始设计
```
