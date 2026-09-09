# 应用场景完整示例

## 场景 1: 智能客服（快速打断）

```javascript
// 用户不想听完整回复，直接问新问题
let isRecording = false;

micButton.onclick = () => {
  if (!isRecording) {
    // 打断当前播报
    avatar.interrupt();
    
    // 开始新的录音
    recorder.startRecord(60 * 1000, null, { nlp: true });
    isRecording = true;
  } else {
    recorder.stopRecord();
    isRecording = false;
  }
};
```

## 场景 2: 实时对话（全双工）

```javascript
// 像人与人对话一样，边说边识别
async function startRealTimeConversation() {
  // 启用全双工
  avatar.setGlobalParams({
    asr: { full_duplex: true }
  });
  
  // 开始持续录音
  await avatar.writeText('', { nlp: true, full_duplex: true });
  recorder.startRecord(300 * 1000, null, { 
    nlp: true, 
    vad: true 
  });
  
  // 实时显示识别结果
  avatar.on(SDKEvents.asr, (data) => {
    if (data.type === 'partial') {
      updateTranscript(data.text);  // 实时更新
    }
  });
}
```

## 场景 3: 紧急消息打断

```javascript
// 接到紧急通知，立即打断当前播报
function showUrgentMessage(message) {
  // 打断当前播报
  avatar.interrupt();
  
  // 播报紧急消息
  avatar.writeText(`紧急通知：${message}`, { nlp: false });
}
```

## 场景 4: 交互式教学

```javascript
// 学生可以随时打断虚拟教师提问
document.addEventListener('keypress', (e) => {
  if (e.key === ' ') {  // 按空格键打断
    avatar.interrupt();
    startRecording();  // 开始提问
  }
});
```
