# 打断播报 - 多平台实现

## 立即中断当前播报

### Web
```javascript
// 打断正在进行的播报
avatar.interrupt();

// 示例：用户点击"停止"按钮
stopButton.onclick = () => {
  avatar.interrupt();
  console.log('已打断播报');
};
```

### Android
```java
// 打断播报
controller.interrupt();

// 示例：用户点击停止按钮
stopButton.setOnClickListener(v -> {
    controller.interrupt();
    Log.d(TAG, "已打断播报");
});
```

### iOS
```objc
// 打断播报
[controller interrupt];

// 示例：用户点击停止按钮
- (void)onStopButtonClicked {
    [controller interrupt];
    NSLog(@"已打断播报");
}
```

---

## 打断后继续新内容

```javascript
// Web - 打断后立即播报新内容
avatar.interrupt();
await avatar.writeText('我来回答您的新问题', { nlp: false });

// Android
controller.interrupt();
controller.writeText("我来回答您的新问题", null);

// iOS
[controller interrupt];
[controller writeText:@"我来回答您的新问题" textParams:nil];
```

---

## 打断模式配置

```javascript
// Web - 配置交互模式
avatar.setGlobalParams({
  dispatch: {
    interactive_mode: 1  // 0=追加模式, 1=打断模式
  }
});

// interactive_mode = 1 时，新的播报会自动打断正在进行的播报
```

**交互模式对比**:
- **追加模式 (0)**: 新播报排队等待，不打断当前播报
- **打断模式 (1)**: 新播报立即打断当前播报
