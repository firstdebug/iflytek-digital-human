# Android 语音交互实现

## 权限配置

**Android**: 运行时权限申请
```xml
<!-- AndroidManifest.xml -->
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
```
```java
// 运行时申请
if (ContextCompat.checkSelfPermission(this, RECORD_AUDIO) != GRANTED) {
    ActivityCompat.requestPermissions(this, new String[]{RECORD_AUDIO}, 1);
}
```

---

## 快速接入

```java
// 1. 创建录音器
AudioRecorder recorder = new AudioRecorder(
    MediaRecorder.AudioSource.MIC,
    16000,  // 采样率必须 16000
    AudioFormat.ENCODING_PCM_16BIT,
    AudioFormat.CHANNEL_IN_MONO
);
recorder.init();

// 2. 监听事件
@Override
public void onEvent(String eventType, String eventData) {
    if ("asr".equals(eventType)) {
        // ASR 识别结果
        Log.d(TAG, "识别: " + eventData);
    } else if ("nlp".equals(eventType)) {
        // NLP 回复
        Log.d(TAG, "回复: " + eventData);
    }
}

// 3. 开始录音
AudioParams audioParams = new AudioParams();
audioParams.setNlp(true);
controller.startAudioInteract(audioParams);
recorder.startRecord();

// 录音数据回调
recorder.setDataAvailable(pcmData -> {
    controller.writeAudioFrame(pcmData);
});

// 4. 停止录音
recorder.stopRecord();
controller.stopAudioInteract();
```

---

## 麦克风权限被拒绝处理

引导用户到系统设置开启权限。
