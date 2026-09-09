# 虚拟人 SDK 使用约定

> 当任务涉及虚拟人 SDK、WebSocket、播放器、录音器时装载。

## 初始化顺序(强制)

必须严格按此顺序,否则连接失败:

```
1. new AvatarPlatform()
2. setApiInfo()      — 凭据
3. setGlobalParams() — 全局参数(必须在 start 前)
4. on(事件监听)      — 必须在 start 前注册
5. start()           — 建立连接、拉流
```

- 事件监听器必须在 `start()` 之前注册,否则漏事件
- 参数配置必须在 `start()` 之前,连接后修改无效

## 参数硬约束

| 参数 | 约束 | 违反后果 |
|------|------|---------|
| `stream.bitrate` | **≥ 200**(推荐 2000) | ConnectError 参数校验失败 |
| `stream.protocol` | xrtc / webrtc / rtmp | 播放器创建失败 |
| `avatar.width/height` | 4 的倍数 | 渲染异常 |
| 音频采样率 | **16000 Hz** | 口型不同步/无声 |
| 音频位深 | 16 bit | 识别失败 |
| 音频声道 | 单声道 mono | 识别失败 |

## 事件监听完整性

至少监听这 4 个,缺一不可:
- `connected` — 连接成功
- `error` — 错误处理(必须有,否则用户看不到错误原因)
- `disconnected` — 断线处理
- `stream_start` — 推流开始(需视频时)

## NLP 数据解析(高频陷阱)

NLP 回复的 `answer` 是**对象**,不是字符串。直接用会显示 `[object Object]`。

正确提取优先级:
```
data.displayContent
→ data.answer.displayContent  (最常见)
→ data.answer.text
→ data.answer (字符串时)
```

流式 NLP 每帧推送的是**累积内容**(非增量),前端应**复用同一消息框更新**,而非每帧新建框。

## 资源释放(强制)

页面/组件销毁前必须按序释放,否则占用授权路数:
```
1. recorder.stopRecord()  — 先停录音
2. avatar.stop()          — 再停会话
3. avatar.destroy()       — 最后销毁
```

## 透明背景(双重配置)

必须同时配置两处,且协议为 xrtc:
- `stream.alpha = 1`(服务端流参数)
- `player.alpha = true`(播放器参数)

超拟人形象不支持透明背景。

## 安全约束

**凭据**:
- 生产环境**禁止**前端硬编码 apiSecret
- 凭据存 `.env`,且 `.env` 必须进 `.gitignore`
- 推荐服务端签名,前端只传 signedUrl
- 日志中对 apiSecret、signature 脱敏(显示 `****`)

**网络**:
- 使用官方 WSS 地址,不开启 `trustAllSSLCertificates`
- 有 CSP 时放行接口域名的 `connect-src`

**隐私**:
- 不打印用户语音、文本等隐私内容到日志
- 不将用户数据上传到非授权服务

## 其他高频陷阱(写代码前规避)

上文参数/事件/透明背景之外,还有几个反复踩到的坑:

| 陷阱 | 现象 | 规避 |
|------|------|------|
| 浏览器无声音 | 有画面无声,控制台 `playNotAllowed` | 监听 `PlayerEvents.playNotAllowed`,引导用户点击后调 `player.resume()`(浏览器安全策略,无法绕过) |
| 录音需 HTTPS | `navigator.mediaDevices` 为 undefined | 录音必须在 HTTPS 或 localhost;开发用 localhost,生产必须 HTTPS |
| SDK 是 ESM | 直接 `<script>` 引入报错 | 用 `import` 或 `<script type="module">`,动态导入加 `/* @vite-ignore */` |
| sceneId 未发布 | 连接报错 10121 | 控制台创建接口服务后必须点"发布",appid 才能用 |
| 并发路数超限 | 报错 11203 | 默认仅 1 路;上一会话未 `destroy()` 就开新会话会超限,确保按序释放 |

## 版本变更

SDK 版本变更需重新走 `avatar-preflight` 环境门禁,重新验证。

---

> 本文件是虚拟人领域约束的**唯一权威源**(合并原 security.md、common-pitfalls.md)。
> avatar-executing / avatar-code-writer / avatar-troubleshoot 等 skill 涉及 SDK 时应参照本文件。
