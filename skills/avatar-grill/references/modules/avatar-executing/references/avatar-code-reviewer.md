# SDK 静态审查清单

## 🚦 Android 首次接入必查清单（HARD-GATE，逐条 grep 核对）

主 Agent 检查 Android SDK 集成代码时，**先读** `android-sdk-build-playbook.md`，再逐条核对以下项。
任一项不过即为 Critical，修复并重新验证（这些都是真机验证过、漏了会致命的坑）：

| # | 检查项 | 判定方法 | 不过的后果 |
|---|--------|----------|-----------|
| C1 | **失真 API 零命中** | grep `createStreamPlayer\|sendText\|onNlpResult\|onAsrResult\|onAvatarReady\|writeAudioFrame\|startAudioInteract\|setApiKey(` | 编译失败或运行崩溃 |
| C2 | **NLP 走对路** | 交互用 `writeText(text, TextParams)` 且该 `TextParams.setNlp(true)` | 裸 writeText=纯朗读，虚拟人不回答，知识库/DeepSeek 全失效 |
| C3 | **答案从 extra 取** | `onResult` 里解析的是 `extra`（JSON `answer.text`），不是 `new String(data,...)` | data 常为空，答案永远显示不出来 |
| C4 | **渲染容器不是 IjkVideoView** | layout 里渲染区是普通 `FrameLayout`，且代码有 `createPlayer(...)`+`setRenderArea(容器)` | XML 直接声明 IjkVideoView → inflate 崩溃；漏 setRenderArea → 黑屏 |
| C5 | **传递依赖齐全** | `app/build.gradle` 显式含 `okhttp` + `gson` | 启动即 `NoClassDefFoundError: okhttp3.WebSocketListener` |
| C6 | **初始化顺序** | `setGlobalParams` 在 `setStreamPlayer` 之前；`setServerUrl` 已调用 | 顺序反=bindAvatar 失败；漏 serverUrl=600003 |
| C7 | **Stream 挂 Avatar** | `avatar.setStream(stream)`，不是 `params.setStream(...)` 顶层 | 参数不生效 |
| C8 | **资产来自探测** | avatarId/vcn 是 auth-avatar 探测值，非硬编码历史值（如 x4_yezi/110117026） | 连上即断（10120/10121） |

> 反例记录（真实踩过）：某次评审放过了 C2（裸 writeText）和 C3（从 data 取答案），导致
> 虚拟人能连上、会念问题，但从不基于知识库回答——RAG 整条链路形同虚设却"看起来能跑"。
> 这类"表面正常"缺陷最危险，C2/C3 必须逐字核对，不能凭"看起来调了 writeText"放行。

---

**特殊检查**:

#### 1. 检查虚拟人专有陷阱

**透明背景配置检查**:
```javascript
// ❌ 错误: 只配置了一处
stream.setAlpha(1);
// 缺少播放器参数配置

// ✓ 正确: 两处都配置
stream.setAlpha(1);
playerParams.setBgAlpha(true);
```

**事件监听检查**:
```javascript
// ❌ 错误: 缺少关键事件
avatar.on(SDKEvents.connected, ...);
// 缺少 error 事件监听

// ✓ 正确: 必需事件都监听
avatar.on(SDKEvents.connected, ...);
avatar.on(SDKEvents.error, ...);
avatar.on(SDKEvents.disconnected, ...);
```

#### 2. 检查配置正确性

**音频参数匹配检查**:
```javascript
// ❌ 错误: 采样率不匹配
const recorder = createRecorder({ sampleRate: 44100 });  // 错误
// 虚拟人 SDK 要求 16000

// ✓ 正确
const recorder = createRecorder({ sampleRate: 16000 });
```

**协议与特性匹配检查**:
```javascript
// ❌ 错误: WebRTC 不支持透明背景
stream.protocol = 'webrtc';
stream.alpha = 1;  // 无效

// ✓ 正确
stream.protocol = 'xrtc';
stream.alpha = 1;
```

**[Web] bitrate /1024 陷阱检查（HARD）**:
```javascript
// ❌ 错误: 只配顶层 stream，靠 bitrate:2000 —— SDK 会 floor(2000/1024)=1，报 "must be >= 200"
avatar.setGlobalParams({ stream: { protocol:'xrtc', fps:25, bitrate:2000 },
                         avatar: { avatar_id, width:720, height:1280 } });  // 缺 avatar.stream

// ✓ 正确: 手写 avatar.stream，bitrate 原样发送（WYSIWYG），单位 kbps [200,20000]
avatar.setGlobalParams({
  stream: { protocol:'xrtc', fps:25, bitrate:2000 },
  avatar: { avatar_id, width:720, height:1280,
            stream: { protocol:'xrtc', fps:25, bitrate:2000, alpha:0 } },  // ← 必查
  tts: { vcn, speed:50, pitch:50, volume:50 },
});
// 审查要点：web 平台的 setGlobalParams 必须含 avatar.stream 且 4 字段齐全。
// 详见 web-sdk-build-playbook.md §3 字段锁定表。
```

**[Web] apiSecret 泄露检查（HARD）**:
```javascript
// ❌ 错误: 向 Web 前端的 setApiInfo 传任何 Key/Secret 或裸 server URL
// 即使只写占位符，模型也可能把它复制进真实实现，因此这里不提供危险调用示例。

// ✓ 正确: 后端签名，前端只拿 signedUrl
avatar.setApiInfo({ signedUrl, appId, sceneId });
// 审查要点：前端 bundle 中 grep apiSecret 必须无命中。
```

#### 3. 检查资源管理

**资源释放检查**:
```javascript
// ❌ 错误: 未释放资源
// Activity onDestroy 没有调用 controller.destroy()

// ✓ 正确
@Override
protected void onDestroy() {
    super.onDestroy();
    if (controller != null) {
        controller.stop();
        controller.destroy();
    }
}
```

**录音器停止检查**:
```javascript
// ❌ 错误: 录音中直接销毁
controller.destroy();

// ✓ 正确: 先停止录音
if (recorder.isRecording()) {
    recorder.stopRecord();
}
controller.destroy();
```

#### 4. 检查错误处理

**错误码处理检查**:
```javascript
// ❌ 错误: 没有错误处理
avatar.start();

// ✓ 正确: 捕获并处理错误
try {
  await avatar.start();
} catch (err) {
  console.error('启动失败:', err.code, err.message);
  switch(err.code) {
    case '10110': alert('appId 错误'); break;
    case '10113': alert('apiSecret 错误'); break;
    // ...
  }
}
```
