# 应用场景与常见问题

## 应用场景

### 场景 1: 互动展示（导览、讲解）

```javascript
// 展厅导览虚拟人
async function tourGuide() {
  // 欢迎环节
  await avatar.writeText('欢迎来到科技馆', { nlp: false });
  await avatar.writeCmds([{ cmd: 'action', params: { action_id: 'welcome' } }]);
  
  // 讲解环节
  await avatar.writeText('接下来我为大家介绍展品', { nlp: false });
  // 使用 AIR 自动匹配解释手势
  
  // 告别环节
  await avatar.writeText('期待您的下次光临', { nlp: false });
  await avatar.writeCmds([{ cmd: 'action', params: { action_id: 'bow' } }]);
}
```

### 场景 2: 客服场景（强调、安抚）

```javascript
// 根据对话情绪触发动作
avatar.on(SDKEvents.nlp, (data) => {
  if (data.answer.includes('非常抱歉')) {
    // 触发道歉手势
    avatar.writeCmds([{ cmd: 'action', params: { action_id: 'bow' } }]);
  } else if (data.answer.includes('请注意')) {
    // 触发强调手势
    avatar.writeCmds([{ cmd: 'action', params: { action_id: 'emphasize' } }]);
  }
});
```

### 场景 3: 直播场景（主动互动）

```javascript
// 定时触发互动动作
setInterval(() => {
  const randomAction = ['wave', 'nod', 'think'][Math.floor(Math.random() * 3)];
  avatar.writeCmds([{ cmd: 'action', params: { action_id: randomAction } }]);
}, 30000);  // 每 30 秒一次
```

---

## 常见问题

### 1. 动作不生效

**原因**:
- 形象不支持动作控制（检查是否为标准虚拟人）
- action_id 拼写错误或不存在

**解决**:
```javascript
// 检查形象是否支持动作
avatar.on(SDKEvents.avatar_ready, (data) => {
  if (!data.actions || data.actions.length === 0) {
    console.warn('当前形象不支持动作控制');
  }
});
```

### 2. AIR 不生效

**原因**:
- 未启用 AIR (`air: true`)
- 形象不支持 AIR

**解决**:
```javascript
// 确认 AIR 已启用
avatar.setGlobalParams({
  air: { air: true }
});
```

### 3. 动作与播报不同步

**原因**: 独立动作与播报时机不匹配

**解决**: 使用 AIR 自动匹配，或监听 `frame_start` 事件后触发动作

```javascript
avatar.on(SDKEvents.frame_start, () => {
  // 播报开始时触发动作
  avatar.writeCmds([{ cmd: 'action', params: { action_id: 'wave' } }]);
});
```

### 4. 动作过于频繁

**原因**: AIR 模式下每句话都可能触发动作

**解决**: 调整话术或关闭 AIR，改用手动触发
