# iOS 语音交互实现

## 权限配置

**iOS**: Info.plist 配置
```xml
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>
```

---

## 快速接入

```objc
// 1. 创建录音器
AudioRecorder *recorder = [[AudioRecorder alloc] initWithDelegate:self];

// 2. 监听事件
- (void)avatarOnEvent:(AvatarEventType)eventType eventData:(NSString *)eventData {
    if (eventType == AvatarEventType_asr) {
        NSLog(@"识别: %@", eventData);
    } else if (eventType == AvatarEventType_nlp) {
        NSLog(@"回复: %@", eventData);
    }
}

// 3. 开始录音
AudioParams *params = [AudioParams new];
params.nlp = YES;
[controller startAudioInteract:params];
[recorder startRecord];

// 录音数据回调
- (void)didReceiveAudioData:(NSData *)audioData {
    [controller writeAudioFrame:audioData];
}

// 4. 停止录音
[recorder stopRecord];
[controller stopAudioInteract];
```

---

## 麦克风权限被拒绝处理

引导用户到系统设置开启权限。
