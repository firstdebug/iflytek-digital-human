# 快速接入

文本交互（经过 NLP/大模型）的多平台快速接入代码。

## Web
```javascript
// 文本交互（经过 NLP）
await avatar.writeText('请介绍一下你自己', { nlp: true });

// 监听 NLP 回复
avatar.on(SDKEvents.nlp, (data) => {
  console.log('NLP 理解结果:', data.answer);
  // 虚拟人会自动播报 answer 内容
});

// 监听播报事件
avatar.on(SDKEvents.frame_start, (data) => {
  console.log('开始播报 NLP 回复');
});
```

## Android
```java
// 1. 配置文本交互参数
TextParams textParams = new TextParams();
textParams.setNlp(true);  // 启用 NLP

// 2. 发送文本
controller.writeText("请介绍一下你自己", textParams);

// 3. 监听 NLP 回复
@Override
public void onEvent(String eventType, String eventData) {
    if ("nlp".equals(eventType)) {
        // 解析 NLP 回复
        JSONObject nlpData = new JSONObject(eventData);
        String answer = nlpData.optString("answer");
        Log.d(TAG, "NLP回复: " + answer);
        // 虚拟人会自动播报 answer
    }
}
```

## iOS
```objc
// 1. 配置文本交互参数
TextParams *textParams = [TextParams new];
textParams.nlp = YES;  // 启用 NLP

// 2. 发送文本
[controller writeText:@"请介绍一下你自己" textParams:textParams];

// 3. 监听 NLP 回复
- (void)avatarOnEvent:(AvatarEventType)eventType eventData:(NSString *)eventData {
    if (eventType == AvatarEventType_nlp) {
        // 解析 NLP 回复
        NSDictionary *nlpData = [NSJSONSerialization JSONObjectWithData:...];
        NSString *answer = nlpData[@"answer"];
        NSLog(@"NLP回复: %@", answer);
        // 虚拟人会自动播报 answer
    }
}
```
