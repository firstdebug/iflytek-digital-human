# avatar-code-writer 领域适配器 (Step 3.2)

## 🚦 HARD-GATE：写任何代码前必读（Android / Web 首次接入）

**你是被派发来写代码的子 agent，不共享主 agent 上下文。** 主 agent 读没读过 playbook 与你无关——
**你必须自己先读**下面这份权威 API 文档全文，再动手：

| 平台 | 唯一权威 API 文档（先 Read 全文） | 逐字模板 |
|------|-----------------------------------|----------|
| Android | `skills/avatar-executing/references/android-sdk-build-playbook.md` | `android-mainactivity-template.java` |
| Web | `skills/avatar-executing/references/web-sdk-build-playbook.md` | playbook §6 |

**禁止事项**：
- ❌ 不读 playbook 就凭记忆/通用知识写 SDK 代码
- ❌ 不照 `integration-guides/android.md`（人工简化失真版，含不存在的 API）
- ❌ 不用主 agent 手搓的 `sdk-api-notes.md` 之类替代 playbook（可作补充，但 playbook 优先）

**Android 失真 API 黑名单（真实 SDK 中不存在，写出来必崩，写完自查 grep 必须零命中）**：
`createStreamPlayer` `sendText` `onNlpResult` `onAsrResult` `onAvatarReady`
`writeAudioFrame` `startAudioInteract` `setApiKey(`（真实是小写 `setApikey`）

### Android 五个高频致命坑（javap 反编译 + 真机验证，逐条对照）

1. **NLP/知识库不生效**：文本交互必须 `writeText(text, TextParams)` 且 `TextParams.setNlp(true)`。
   裸 `writeText(text)` 默认 `mNlp=false` = **纯朗读**，不走 NLP/DeepSeek/知识库——虚拟人只会
   把问题原样念一遍。这是"能连上、会说话、但从不回答"的根因。
2. **答案取不到**：NLP 结果在 `onResult(type, byte[] data, String extra)` 的 **`extra` JSON**
   里（`{"answer":{"text":"..."},"status":1|2,"request_id":"...","service":"docqa|openai"}`），
   **不在 `data`**（data 常为空）。按 `request_id` 把 status=1 分片累加，status=2 收尾。
   判定命中知识库看 extra 的 `"service":"docqa"`。
3. **inflate 崩溃**：**不要**在 XML 里直接声明 `IjkVideoView`（其构造函数依赖 SDK/native 初始化，
   inflate 时抛 `InflateException`）。用普通 `FrameLayout` 容器 + `StreamPlayerFactory.createPlayer(ctx,"xrtc")`
   → `player.setRenderArea(容器)`，SDK 自己往容器里 addView 渲染面。漏 setRenderArea = 黑屏。
4. **运行时 NoClassDefFoundError**：avatar-core AAR 不带传递依赖，`app/build.gradle` 必须显式加
   `okhttp`(WebSocket 用) + `gson`，否则启动即 `NoClassDefFoundError: okhttp3.WebSocketListener`。
5. **顺序 + serverUrl**：`setGlobalParams` 必须在 `setStreamPlayer` 之前（后者 bindAvatar 依赖前者）；
   `AvatarPlatformConfig.Builder.setServerUrl(...)` 必设，漏了报 600003；Stream 挂在 Avatar 下
   （`avatar.setStream(stream)`），不是 AvatarParams 顶层。bitrate 为裸 int(kbps)，Android **无** /1024 陷阱（那是 Web 的坑）。

---

**特殊能力**:

#### 1. 理解虚拟人 SDK 文档
```javascript
// 自动加载相关文档章节
const relevantDocs = loadSDKDocs(step.topic);

// 理解 API 语义
if (step.topic === 'sdk_initialization') {
  // 知道 Web 需要 setApiInfo
  // 知道 Android 需要 AvatarPlatform.initialize
  // 知道 iOS 需要 initializeConfig
}
```

#### 2. 正确处理 WebSocket 鉴权
```javascript
// Web 签名生成
const signature = hmacSha256(apiSecret, origin);
const authorization = `api_key="${apiKey}", algorithm="hmac-sha256", ...`;
const authBase64 = base64Encode(authorization);

// 知道 date 必须是 UTC GMT 格式
// 知道 authorization 需要 URL 编码
```

#### 3. 正确配置播放器参数
```javascript
// 透明背景需要同时配置两处
stream.setAlpha(1);  // 服务端流参数
playerParams.setBgAlpha(true);  // 播放器参数

// 知道 XRTC 协议才支持透明背景
if (needsTransparentBg && protocol !== 'xrtc') {
  WARN("透明背景仅 XRTC 协议支持");
}
```

#### 4. 正确处理事件回调
```javascript
// 知道必需监听的事件
avatar.on(SDKEvents.connected, ...);  // 连接成功
avatar.on(SDKEvents.error, ...);      // 错误处理
avatar.on(SDKEvents.stream_start, ...); // 推流开始

// 知道判断播报结束的正确方式
avatar.on(SDKEvents.frame_stop, (data) => {
  if (data.vmr_status === 2) {
    // 播报结束
  }
});
```

#### 5. 遵循平台最佳实践
```javascript
// Web: 处理浏览器自动播放限制
player.on(PlayerEvents.playNotAllowed, () => {
  document.addEventListener('click', () => player.resume(), { once: true });
});

// Android: 运行时权限申请
if (ContextCompat.checkSelfPermission(this, RECORD_AUDIO) != GRANTED) {
  ActivityCompat.requestPermissions(this, new String[]{RECORD_AUDIO}, 1);
}

// iOS: AVAudioSession 配置
[[AVAudioSession sharedInstance] 
    setCategory:AVAudioSessionCategoryPlayAndRecord 
    error:nil];
```

---

## 关键落地常量（HARD-GATE，写代码前必读）

以下是从 SDK 反编译核对过的真实值。**不要**依赖 SDK 内置默认值——AAR 里内置的是**测试地址**，直接用会连不上。

### 1. serverUrl 必须显式设置（否则 600003）

生产接入地址（三端一致）：
```
wss://avatar.cn-huadong-1.xf-yun.com/v1/interact
```
- Android: `new AvatarPlatformConfig.Builder().setServerUrl("wss://avatar.cn-huadong-1.xf-yun.com/v1/interact")`
- Web: Node 服务端持有固定 WS_URL 并生成 signedUrl；前端只调用
  `setApiInfo({ signedUrl, appId, sceneId })`
- iOS: `config.serverUrl = @"wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"`

**不设的后果**：SDK 用内置 `wss://test.xfyousheng.com/...` 测试地址，WebSocket 握手报
`600003 / "Expected HTTP 101 response but was 200"`。这是最常见的"初始化成功但连不上"根因。

### 2. 接口场景（SDK/WebAPI）必须客户端传 avatarId + vcn

`xfyun_interface.py create` 建出的接口场景**不含形象/发音人**（区别于 Web模板/直播场景，
后者在平台侧已配好）。SDK 端必须在 `AvatarParams` 里显式设置，否则"连上即断"
（server_connect_success 后立刻 server_disconnect）：
```java
AvatarParams.Avatar avatar = new AvatarParams.Avatar();
avatar.setAvatarId(AVATAR_ID);   // 见下方"资产授权"
AvatarParams.TTS tts = new AvatarParams.TTS();
tts.setVcn(VCN);
params.setAvatar(avatar); params.setTTS(tts);
```

### 3. 资产授权：avatarId/vcn 必须先授权给 appId，且默认值因账号而异

形象/发音人在使用前必须经 `app/auth_asset` 授权给该 appId（assetType=1形象/3发音人，
assetScene=1）。**关键**：不同账号可授权的资产不同，**不要硬编码猜 ID**。正确做法是
调 `xfyun_interface.py list-assets <appId>` 或授权探测，取该账号**实际授权成功**的 ID。
（历史上 live/template 工具里硬编码的 `110117026` 在部分账号会授权失败，务必以探测结果为准。）
