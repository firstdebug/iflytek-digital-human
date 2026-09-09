# 查询可用动作列表与动作事件监听

## 查询可用动作列表

### 获取形象支持的动作

```javascript
// Web - 从 avatar_ready 事件中获取
avatar.on(SDKEvents.avatar_ready, (data) => {
  if (data.actions) {
    console.log('支持的动作:', data.actions);
    // 输出: ["wave", "nod", "bow", "think", "welcome", ...]
  }
});

// Android
@Override
public void onEvent(String eventType, String eventData) {
    if ("avatar_ready".equals(eventType)) {
        JSONObject data = new JSONObject(eventData);
        JSONArray actions = data.optJSONArray("actions");
        Log.d(TAG, "支持的动作: " + actions);
    }
}

// iOS
- (void)avatarOnEvent:(AvatarEventType)eventType eventData:(NSString *)eventData {
    if (eventType == AvatarEventType_avatar_ready) {
        NSDictionary *data = [NSJSONSerialization JSONObjectWithData:...];
        NSArray *actions = data[@"actions"];
        NSLog(@"支持的动作: %@", actions);
    }
}
```

---

## 动作事件监听

### 监听动作开始和结束

```javascript
// Web
avatar.on(SDKEvents.action_start, (data) => {
  console.log('动作开始:', data.action_id);
});

avatar.on(SDKEvents.action_stop, (data) => {
  console.log('动作结束:', data.action_id);
});

// Android
@Override
public void onEvent(String eventType, String eventData) {
    if ("action_start".equals(eventType)) {
        JSONObject data = new JSONObject(eventData);
        Log.d(TAG, "动作开始: " + data.optString("action_id"));
    } else if ("action_stop".equals(eventType)) {
        JSONObject data = new JSONObject(eventData);
        Log.d(TAG, "动作结束: " + data.optString("action_id"));
    }
}

// iOS
- (void)avatarOnEvent:(AvatarEventType)eventType eventData:(NSString *)eventData {
    if (eventType == AvatarEventType_action_start) {
        // 动作开始
    } else if (eventType == AvatarEventType_action_stop) {
        // 动作结束
    }
}
```
