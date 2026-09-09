# 云端字幕启用

由服务端生成，通过 `subtitle_info` 事件回调返回。透明背景和 3D 形象不支持云端字幕。

## 启用云端字幕

### Web
```javascript
// 全局启用字幕
avatar.setGlobalParams({
  subtitle: {
    subtitle: true  // 启用字幕
  }
});

// 监听字幕事件
avatar.on(SDKEvents.subtitle_info, (data) => {
  console.log('字幕:', data.text);
  displaySubtitle(data.text);
});
```

### Android
```java
// 配置字幕参数
AvatarParams.Subtitle subtitle = new AvatarParams.Subtitle();
subtitle.setSubtitle(true);  // 启用字幕

AvatarParams params = new AvatarParams();
params.setSubtitle(subtitle);
controller.setGlobalParams(params);

// 监听字幕事件
@Override
public void onEvent(String eventType, String eventData) {
    if ("subtitle_info".equals(eventType)) {
        JSONObject data = new JSONObject(eventData);
        String text = data.optString("text");
        Log.d(TAG, "字幕: " + text);
        displaySubtitle(text);
    }
}
```

### iOS
```objc
// 配置字幕参数
AvatarParamsSubtitle *subtitle = [AvatarParamsSubtitle new];
subtitle.subtitle(YES);  // 启用字幕

AvatarParams *params = [AvatarParams new];
params.subtitle(subtitle);
controller.globalParams = params;

// 监听字幕事件
- (void)avatarOnEvent:(AvatarEventType)eventType eventData:(NSString *)eventData {
    if (eventType == AvatarEventType_subtitle_info) {
        NSDictionary *data = [NSJSONSerialization JSONObjectWithData:...];
        NSString *text = data[@"text"];
        NSLog(@"字幕: %@", text);
        [self displaySubtitle:text];
    }
}
```

## 字幕数据结构

```json
{
  "text": "欢迎来到虚拟人展厅",
  "begin_time": 1000,
  "end_time": 3000,
  "word_list": [
    {"word": "欢迎", "begin_time": 1000, "end_time": 1500},
    {"word": "来到", "begin_time": 1500, "end_time": 2000},
    {"word": "虚拟人", "begin_time": 2000, "end_time": 2500},
    {"word": "展厅", "begin_time": 2500, "end_time": 3000}
  ]
}
```

**字段说明**:
- `text`: 完整字幕文本
- `begin_time`: 字幕开始时间（ms）
- `end_time`: 字幕结束时间（ms）
- `word_list`: 逐字时间戳（用于逐字高亮）
