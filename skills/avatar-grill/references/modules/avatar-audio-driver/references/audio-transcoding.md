# 音频转码到 16kHz PCM

音频格式不匹配会导致口型不同步或无声音。若源音频不是 16kHz PCM，必须先转码。

## 音频转码示例

```javascript
// Web - 使用 AudioContext 重采样到 16kHz
async function resampleTo16k(audioBuffer) {
  const offlineCtx = new OfflineAudioContext(
    1,  // 单声道
    audioBuffer.duration * 16000,
    16000  // 目标采样率
  );
  const source = offlineCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineCtx.destination);
  source.start();
  const resampled = await offlineCtx.startRendering();
  return float32ToPCM16(resampled.getChannelData(0));
}

// Float32 转 PCM16
function float32ToPCM16(float32Array) {
  const pcm16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return pcm16.buffer;
}
```
