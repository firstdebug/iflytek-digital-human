# 常见问题排查

## 1. 打断不生效

**原因**: 播报已结束或未在播报状态

**解决**: 检查播报状态

```javascript
let isSpeaking = false;

avatar.on(SDKEvents.frame_start, () => {
  isSpeaking = true;
});

avatar.on(SDKEvents.frame_stop, () => {
  isSpeaking = false;
});

// 仅在播报时才打断
if (isSpeaking) {
  avatar.interrupt();
}
```

## 2. 全双工未生效

**原因**:
- 未开通全双工服务能力
- 未启用 `full_duplex: true`

**解决**:
```javascript
// 1. 确认启用全双工
avatar.setGlobalParams({
  asr: { full_duplex: true }
});

// 2. 检查服务能力
// 登录平台控制台确认已开通全双工
```

## 3. 实时识别延迟高

**原因**: 网络延迟或音频上传慢

**优化**:
```javascript
// 1. 减小音频帧大小（更频繁上传）
const recorder = avatar.createRecorder({ 
  sampleRate: 16000,
  frameSize: 640  // 20ms 一帧（默认 1280 = 40ms）
});

// 2. 检查网络质量
```

## 4. VAD 误触发

**原因**: 环境噪音或灵敏度设置

**优化**:
```javascript
// 调整 VAD 参数（需服务端支持）
avatar.setGlobalParams({
  asr: {
    vad_threshold: 0.3  // 降低灵敏度（0-1，默认 0.2）
  }
});
```
