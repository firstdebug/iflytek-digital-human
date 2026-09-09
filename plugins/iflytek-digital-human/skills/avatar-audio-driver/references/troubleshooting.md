# 常见问题排查

## 1. 口型不同步

**原因**: 音频采样率不是 16kHz

**解决**: 转码到 16kHz PCM（见 audio-transcoding.md 转码示例）

## 2. 有口型无声音

**原因**:
- 浏览器自动播放限制（Web）
- 音频数据为空或格式错误

**解决**:
```javascript
avatar.on(PlayerEvents.playNotAllowed, () => {
  // 引导用户点击后恢复播放
  showResumeButton(() => player.resume());
});
```

## 3. 音频卡顿

**原因**: 帧过大或推送过快

**解决**: 使用 1280 字节/帧（40ms），控制推送节奏

## 4. 尾帧未推送导致播报不结束

**原因**: 忘记发送 status=2 的尾帧

**解决**: 音频结束时务必推送尾帧标识
