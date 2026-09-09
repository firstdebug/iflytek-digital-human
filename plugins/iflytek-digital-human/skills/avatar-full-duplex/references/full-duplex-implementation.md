# 全双工语音交互 - 多平台实现

## 启用全双工

### Web
```javascript
// 1. 全局启用全双工
avatar.setGlobalParams({
  asr: {
    full_duplex: true  // 启用全双工
  }
});

// 2. 创建录音器
const recorder = avatar.createRecorder({ 
  sampleRate: 16000,
  vad: true  // 启用 VAD 端点检测
});

// 3. 开始全双工交互
await avatar.writeText('', { 
  nlp: true,
  full_duplex: true 
});

recorder.startRecord(60 * 1000, null, { 
  nlp: true,
  vad: true 
});
```

### Android
```java
// 1. 配置全双工参数
AvatarParams.ASR asr = new AvatarParams.ASR();
asr.setFullDuplex(true);  // 启用全双工

AvatarParams params = new AvatarParams();
params.setASR(asr);
controller.setGlobalParams(params);

// 2. 启动全双工交互
AudioParams audioParams = new AudioParams();
audioParams.setNlp(true);
audioParams.setFullDuplex(true);
controller.startAudioInteract(audioParams);

// 3. 开始录音
recorder.startRecord();
```

### iOS
```objc
// 1. 配置全双工参数
AvatarParamsASR *asr = [AvatarParamsASR new];
asr.fullDuplex(YES);  // 启用全双工

AvatarParams *params = [AvatarParams new];
params.asr(asr);
controller.globalParams = params;

// 2. 启动全双工交互
AudioParams *audioParams = [AudioParams new];
audioParams.nlp = YES;
audioParams.fullDuplex = YES;
[controller startAudioInteract:audioParams];

// 3. 开始录音
[recorder startRecord];
```

---

## 全双工实时识别

```javascript
// Web - 监听实时 ASR 结果
avatar.on(SDKEvents.asr, (data) => {
  if (data.type === 'partial') {
    // 中间结果（实时识别）
    console.log('实时识别:', data.text);
    displayPartialResult(data.text);
  } else if (data.type === 'final') {
    // 最终结果（语句结束）
    console.log('最终识别:', data.text);
    displayFinalResult(data.text);
  }
});

// Android
@Override
public void onEvent(String eventType, String eventData) {
    if ("asr".equals(eventType)) {
        JSONObject data = new JSONObject(eventData);
        String type = data.optString("type");
        String text = data.optString("text");
        
        if ("partial".equals(type)) {
            Log.d(TAG, "实时识别: " + text);
        } else if ("final".equals(type)) {
            Log.d(TAG, "最终识别: " + text);
        }
    }
}
```

---

## VAD 端点检测

```javascript
// Web - 监听语音端点
avatar.on(SDKEvents.vad, (data) => {
  if (data.status === 'speech_start') {
    console.log('检测到语音开始');
    showRecordingIndicator();
  } else if (data.status === 'speech_end') {
    console.log('语音结束');
    hideRecordingIndicator();
    // 自动停止录音
    recorder.stopRecord();
  }
});

// 启动带 VAD 的录音
recorder.startRecord(60 * 1000, null, { 
  nlp: true,
  vad: true  // 启用 VAD
});
```
