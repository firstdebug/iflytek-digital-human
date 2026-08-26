# 权限最佳实践

## 1. 合适的申请时机

**❌ 错误**: 应用启动时立即申请
```javascript
// 不好的做法
app.onLaunch = async () => {
  await requestMicrophonePermission();  // 用户不知道为什么需要
};
```

**✓ 正确**: 用户触发相关功能时申请
```javascript
// 好的做法
voiceButton.onclick = async () => {
  const permission = await requestMicrophonePermission();
  if (permission.granted) {
    startRecording();
  }
};
```

## 2. 清晰的权限说明

**❌ 错误**: 没有说明或说明模糊
```
"应用需要访问您的麦克风"
```

**✓ 正确**: 说明具体用途
```
"虚拟人语音交互功能需要使用麦克风来识别您的语音"
```

## 3. 处理权限拒绝

**提供降级方案**:
```javascript
if (!microphoneGranted) {
  // 提供文本输入替代方案
  showTextInputAlternative();
  showToast("没有麦克风权限，请使用文本输入");
}
```

**引导到设置**:
```javascript
if (permanentlyDenied) {
  showAlert({
    title: "需要麦克风权限",
    message: "请在设置中开启麦克风权限",
    buttons: [
      { text: "去设置", onClick: openSettings },
      { text: "取消" }
    ]
  });
}
```

## 4. 监听权限变化

监听权限变化的平台代码见各平台实现文档：
- Web: `references/web-implementation.md`
- iOS: `references/ios-implementation.md`

---

# 输出格式

## 诊断结果

```yaml
platform: "android"
permission_type: "microphone"
status: "denied"
reason: "用户选择不再询问"
fix:
  - "引导用户到设置中手动开启"
  - "或提供文本输入替代方案"
code_example: "Intent to Settings"
```

## 修复方案

```yaml
steps:
  1:
    action: "配置 Info.plist"
    code: "<key>NSMicrophoneUsageDescription</key>..."
  2:
    action: "运行时申请权限"
    code: "[AVCaptureDevice requestAccessForMediaType:...]"
  3:
    action: "权限拒绝时引导到设置"
    code: "openURL:UIApplicationOpenSettingsURLString"
```
