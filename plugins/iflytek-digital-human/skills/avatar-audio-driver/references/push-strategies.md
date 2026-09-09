# 分帧推送策略

## 1. 流式推送（推荐）

```javascript
// Web - 边合成边推送
async function streamAudio(audioSource) {
  const reader = audioSource.getReader();
  let isFirst = true;
  
  while (true) {
    const { done, value } = await reader.read();
    
    if (done) {
      // 推送尾帧（空数据 + status=2）
      avatar.writeAudio(new ArrayBuffer(0), 2, { nlp: false });
      break;
    }
    
    const status = isFirst ? 0 : 1;
    avatar.writeAudio(value, status, { nlp: false });
    isFirst = false;
  }
}
```

## 2. 整段推送

```javascript
// Web - 一次性推送完整音频
function playFullAudio(pcmData) {
  const frameSize = 1280;  // 40ms
  const totalFrames = Math.ceil(pcmData.byteLength / frameSize);
  
  for (let i = 0; i < totalFrames; i++) {
    const start = i * frameSize;
    const end = Math.min(start + frameSize, pcmData.byteLength);
    const chunk = pcmData.slice(start, end);
    
    let status;
    if (i === 0) status = 0;               // 首帧
    else if (i === totalFrames - 1) status = 2;  // 尾帧
    else status = 1;                        // 中间帧
    
    avatar.writeAudio(chunk, status, { nlp: false });
  }
}
```
