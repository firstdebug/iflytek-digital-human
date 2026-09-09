# 平台接入代码（Web / Android / iOS）

音频驱动的 `writeAudio` 分帧推送接口在各平台的调用方式。frameStatus: 0=首帧, 1=中间帧, 2=尾帧。

## Web
```javascript
// 音频驱动（推送 PCM 数据）
// frameStatus: 0=首帧, 1=中间帧, 2=尾帧

// 首帧
avatar.writeAudio(firstChunk, 0, { nlp: false });
// 中间帧
avatar.writeAudio(middleChunk, 1, { nlp: false });
// 尾帧
avatar.writeAudio(lastChunk, 2, { nlp: false });
```

## Android
```java
// frameStatus: FrameStatus.FIRST / MIDDLE / LAST
AudioParams audioParams = new AudioParams();

// 首帧
controller.writeAudio(firstData, FrameStatus.FIRST, audioParams);
// 中间帧
controller.writeAudio(middleData, FrameStatus.MIDDLE, audioParams);
// 尾帧
controller.writeAudio(lastData, FrameStatus.LAST, audioParams);
```

## iOS
```objc
AudioParams *audioParams = [AudioParams new];

// 首帧 (status = 0)
[controller writeAudio:firstData frameStatus:0 audioParams:audioParams];
// 中间帧 (status = 1)
[controller writeAudio:middleData frameStatus:1 audioParams:audioParams];
// 尾帧 (status = 2)
[controller writeAudio:lastData frameStatus:2 audioParams:audioParams];
```
