# 常见问题排查

## 1. 未收到字幕事件

**原因**:
- 未启用字幕 (`subtitle: true`)
- 透明背景或 3D 形象不支持云端字幕

**解决**:
```javascript
// 检查是否启用
avatar.setGlobalParams({
  subtitle: { subtitle: true }
});

// 透明背景时需自行渲染
if (使用透明背景) {
  avatar.on(SDKEvents.frame_start, (data) => {
    // 手动显示播报文本
    displaySubtitle(data.text);
  });
}
```

## 2. 字幕时机不准确

**原因**: 云端字幕基于服务端时间戳，可能有网络延迟

**解决**: 使用客户端字幕，监听 `frame_start` 事件

```javascript
avatar.on(SDKEvents.frame_start, (data) => {
  displaySubtitle(data.text);
});

avatar.on(SDKEvents.frame_stop, () => {
  hideSubtitle();
});
```

## 3. 字幕显示不全

**原因**: 容器宽度不够或文字过长

**解决**: 使用自动换行和滚动

```css
.subtitle-text {
  max-width: 80%;
  word-wrap: break-word;
  overflow-y: auto;
  max-height: 100px;
}
```
