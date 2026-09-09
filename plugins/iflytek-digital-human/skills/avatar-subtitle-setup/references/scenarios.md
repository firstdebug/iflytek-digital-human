# 应用场景

## 场景 1: 无声环境展示

```javascript
// 商场、展厅等嘈杂或需静音的环境
avatar.setGlobalParams({
  subtitle: { subtitle: true },
  tts: { volume: 0 }  // 静音，仅字幕
});
```

## 场景 2: 听力辅助

```javascript
// 为听力障碍用户提供字幕
avatar.on(SDKEvents.subtitle_info, (data) => {
  displayLargeSubtitle(data.text, {
    fontSize: '28px',
    highContrast: true
  });
});
```

## 场景 3: 语言学习

```javascript
// 显示原文 + 翻译
avatar.on(SDKEvents.subtitle_info, (data) => {
  displaySubtitle(data.text);  // 中文
  translateAndDisplay(data.text);  // 英文翻译
});
```

## 场景 4: 视频录制

```javascript
// 录制虚拟人视频时嵌入字幕
avatar.on(SDKEvents.subtitle_info, (data) => {
  overlaySubtitleOnVideo(data.text, data.begin_time, data.end_time);
});
```
