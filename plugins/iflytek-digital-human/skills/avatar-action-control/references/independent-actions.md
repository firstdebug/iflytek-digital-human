# 独立动作控制

手动触发特定动作，与播报解耦。

## 触发单个动作

### Web
```javascript
// 触发单个动作
await avatar.writeCmds([{
  cmd: 'action',
  params: {
    action_id: 'wave'  // 动作ID
  }
}]);

// 常见动作 ID
const actions = {
  wave: '挥手',
  nod: '点头',
  bow: '鞠躬',
  think: '思考',
  explain: '解释',
  welcome: '欢迎'
};
```

### Android
```java
// 构造动作指令
JSONArray cmds = new JSONArray();
JSONObject actionCmd = new JSONObject();
actionCmd.put("cmd", "action");

JSONObject params = new JSONObject();
params.put("action_id", "wave");
actionCmd.put("params", params);

cmds.put(actionCmd);

// 发送指令
controller.writeCmds(cmds.toString());
```

### iOS
```objc
// 构造动作指令
NSArray *cmds = @[
    @{
        @"cmd": @"action",
        @"params": @{
            @"action_id": @"wave"
        }
    }
];

// 转 JSON 字符串
NSData *jsonData = [NSJSONSerialization dataWithJSONObject:cmds options:0 error:nil];
NSString *cmdsStr = [[NSString alloc] initWithData:jsonData encoding:NSUTF8StringEncoding];

// 发送指令
[controller writeCmds:cmdsStr];
```

---

## 触发动作序列

```javascript
// Web - 依次执行多个动作
await avatar.writeCmds([
  { cmd: 'action', params: { action_id: 'wave' } },      // 先挥手
  { cmd: 'action', params: { action_id: 'bow' } },       // 再鞠躬
  { cmd: 'action', params: { action_id: 'welcome' } }    // 最后欢迎手势
]);
```

---

## 动作与播报结合

```javascript
// 方式 1: 播报时触发动作
await avatar.writeText('大家好！', { nlp: false });
await avatar.writeCmds([{ cmd: 'action', params: { action_id: 'wave' } }]);

// 方式 2: 使用自动动作 AIR（推荐）
// 见 air-auto-actions.md
```
