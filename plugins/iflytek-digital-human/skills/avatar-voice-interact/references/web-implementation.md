# Web 语音交互实现

## 权限配置

**Web**: HTTPS 或 localhost 环境
```javascript
// 检查麦克风权限
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
  alert('浏览器不支持麦克风');
}
```

---

## 快速接入

```javascript
// 1. 创建录音器
const recorder = avatar.createRecorder({ sampleRate: 16000 });

// 2. 监听 ASR 结果
avatar.on(SDKEvents.asr, (data) => {
  console.log('识别结果:', data.text);
});

// 3. 监听 NLP 回复
avatar.on(SDKEvents.nlp, (data) => {
  console.log('NLP回复:', data.answer);
});

// 4. 开始录音（短语音，最长 60 秒）
recorder.startRecord(60 * 1000, () => {
  console.log('录音结束');
}, { nlp: true });

// 5. 停止录音（发送尾帧）
recorder.stopRecord();
```

---

## 进阶配置

### 全双工模式

实时识别，无需等待录音结束。

```javascript
// Web
const recorder = avatar.createRecorder({ sampleRate: 16000 });

// 启用全双工
await avatar.writeText('', { 
  nlp: true,
  full_duplex: true  // 全双工
});

// 开始录音（持续监听）
recorder.startRecord(60 * 1000, null, { 
  nlp: true,
  vad: true  // 语音端点检测
});
```

### VAD 端点检测

自动检测语音开始和结束。

```javascript
// 监听 VAD 事件
avatar.on(SDKEvents.vad, (data) => {
  if (data.status === 'speech_start') {
    console.log('检测到语音');
  } else if (data.status === 'speech_end') {
    console.log('语音结束');
    recorder.stopRecord();  // 自动停止
  }
});
```

---

## UI 交互模式

### 按住说话

```javascript
const button = document.getElementById('record-btn');

button.addEventListener('mousedown', () => {
  recorder.startRecord(60 * 1000, null, { nlp: true });
});

button.addEventListener('mouseup', () => {
  recorder.stopRecord();
});
```

### 点击开始/停止

```javascript
let recording = false;

button.addEventListener('click', () => {
  if (!recording) {
    recorder.startRecord(60 * 1000, null, { nlp: true });
    button.textContent = '停止';
    recording = true;
  } else {
    recorder.stopRecord();
    button.textContent = '开始录音';
    recording = false;
  }
});
```

---

## 麦克风权限被拒绝处理

```javascript
try {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
} catch (err) {
  if (err.name === 'NotAllowedError') {
    alert('请允许麦克风权限');
  }
}
```
