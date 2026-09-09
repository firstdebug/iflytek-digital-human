# 语音交互常见问题排查

## 1. 麦克风权限被拒绝

**Web**:
```javascript
try {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
} catch (err) {
  if (err.name === 'NotAllowedError') {
    alert('请允许麦克风权限');
  }
}
```

**Android/iOS**: 引导用户到系统设置开启权限

---

## 2. 录音无反应

**检查**:
- 采样率必须为 16000
- 音频格式必须为 PCM 16bit
- (Web) 环境必须为 HTTPS 或 localhost

---

## 3. ASR 识别不准确

**优化**:
- 安静环境录音
- 麦克风距离适中
- 清晰发音
- 使用 VAD 端点检测

---

## 4. 录音器启动失败 (错误码 20003)

**原因**:
- 权限未配置或被拒绝
- (iOS) AVAudioSession 配置错误
- 麦克风被其他应用占用

**解决**: 参考 `avatar-permissions-setup`
