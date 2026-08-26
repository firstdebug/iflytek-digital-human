# 应用场景示例

## 场景 1: 接入自研 TTS

```javascript
// 使用自己的 TTS 引擎合成音频，再驱动虚拟人
async function speakWithCustomTTS(text) {
  // 1. 调用自研 TTS
  const audioData = await myTTS.synthesize(text, {
    sampleRate: 16000,  // 必须 16kHz
    format: 'pcm'
  });
  
  // 2. 推送到虚拟人
  playFullAudio(audioData);
}
```

## 场景 2: 播放预录音频

```javascript
// 播放本地录制的音频文件
async function playRecordedAudio(url) {
  const response = await fetch(url);
  const arrayBuffer = await response.arrayBuffer();
  
  // 解码并重采样到 16kHz
  const audioCtx = new AudioContext();
  const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
  const pcm16k = await resampleTo16k(audioBuffer);
  
  playFullAudio(pcm16k);
}
```

## 场景 3: 实时音频流（如直播转虚拟人）

```javascript
// 从 WebSocket 接收音频流并驱动虚拟人
const audioWS = new WebSocket('wss://your-audio-stream');
let isFirst = true;

audioWS.onmessage = (event) => {
  const pcmChunk = event.data;
  const status = isFirst ? 0 : 1;
  avatar.writeAudio(pcmChunk, status, { nlp: false });
  isFirst = false;
};

audioWS.onclose = () => {
  avatar.writeAudio(new ArrayBuffer(0), 2, { nlp: false });
};
```
