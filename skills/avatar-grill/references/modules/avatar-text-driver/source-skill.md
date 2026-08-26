> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。


# avatar-text-driver: 文本驱动

## 功能说明

让虚拟人朗读指定文本内容，适用于播报、导览、客服等场景。

---

## 快速接入

### Web
```javascript
// 文本驱动（不经过 NLP）
await avatar.writeText('你好，欢迎使用虚拟人服务', { nlp: false });

// 监听播报事件
avatar.on(SDKEvents.frame_start, (data) => {
  console.log('开始播报:', data.text);
});

avatar.on(SDKEvents.frame_stop, (data) => {
  if (data.vmr_status === 2) {
    console.log('播报结束');
  }
});
```

### Android
```java
// 文本驱动
controller.writeText("你好，欢迎使用虚拟人服务", null);

// 监听播报事件
@Override
public void onEvent(String eventType, String eventData) {
    if ("frame_start".equals(eventType)) {
        Log.d(TAG, "开始播报");
    } else if ("frame_stop".equals(eventType)) {
        // 解析 eventData JSON，检查 vmr_status === 2
        Log.d(TAG, "播报结束");
    }
}
```

### iOS
```objc
// 文本驱动
[controller writeText:@"你好，欢迎使用虚拟人服务" textParams:nil];

// 监听播报事件
- (void)avatarOnEvent:(AvatarEventType)eventType eventData:(NSString *)eventData {
    if (eventType == AvatarEventType_frame_start) {
        NSLog(@"开始播报");
    } else if (eventType == AvatarEventType_frame_stop) {
        // 解析 eventData JSON，检查 vmr_status === 2
        NSLog(@"播报结束");
    }
}
```

---

## 进阶配置

### 调整播报参数

```javascript
// Web
await avatar.writeText('你好', {
  nlp: false,
  speed: 60,    // 速度 0-100，默认 50
  pitch: 55,    // 音调 0-100，默认 50
  volume: 60    // 音量 0-100，默认 50
});

// Android
TextParams params = new TextParams();
params.setNlp(false);
params.setSpeed(60);
params.setPitch(55);
params.setVolume(60);
controller.writeText("你好", params);

// iOS
TextParams *params = [TextParams new];
params.nlp = NO;
params.speed = 60;
params.pitch = 55;
params.volume = 60;
[controller writeText:@"你好" textParams:params];
```

### 流式文本播报

```javascript
// Web - 按标点拆分长文本，流式播报
const longText = "第一句话。第二句话。第三句话。";
const sentences = longText.split(/[。！？.!?]/);

for (const sentence of sentences) {
  if (sentence.trim()) {
    await avatar.writeText(sentence, { 
      nlp: false,
      stream_nlp: true  // 流式模式
    });
  }
}
```

---

## 常见问题

### 1. 播报没有声音
**原因**: 浏览器自动播放限制（Web）
**解决**: 监听 `playNotAllowed` 事件，引导用户交互后调用 `player.resume()`

### 2. 播报被截断
**原因**: 交互模式设置为"打断"
**解决**: 设置 `dispatch.interactive_mode = 0` (追加模式)

### 3. 播报延迟高
**原因**: 网络延迟或文本过长
**解决**: 
- 检查网络质量
- 拆分长文本为多次播报
- 使用流式模式

---

