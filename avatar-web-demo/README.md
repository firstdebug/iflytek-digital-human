# 虚拟人 Web SDK Demo

讯飞虚拟人 Web SDK 集成演示项目。文字、语音、动作和透明背景代码已实现；浏览器运行时仍需完成连接、首帧和目标交互验证。

## 功能特性

✅ **文字对话** - 用户通过文字输入与虚拟人对话
✅ **语音交互** - 点击开始/停止模式的语音对话
✅ **动作控制** - 控制虚拟人做出特定动作（点头、挥手等）
✅ **透明背景** - 使用 XRTC 协议支持透明背景
✅ **服务端签名** - apiSecret 在服务端，确保安全

## 项目结构

```
avatar-web-demo/
├── server.js          # Node.js 后端（签名 + 静态托管）
├── package.json       # 项目依赖
├── .env               # 凭据配置（不提交到 Git）
├── .gitignore
├── public/
│   ├── index.html     # 前端页面
│   ├── app.js         # SDK 集成代码
│   └── style.css      # 样式
└── sdk/               # 已校验的 Web SDK
    └── avatar-web-sdk/avatar-sdk-web_3.2.3.1002/
```

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 校验 SDK

SDK 已存在，入口为：

```text
sdk/avatar-web-sdk/avatar-sdk-web_3.2.3.1002/esm/index.js
```

SDK 路径和 SHA-256 记录在 `.runtime/sdk-artifact.json`；重新校验请运行插件的 `tools/sdk_artifact.py ensure`，不要依据文档链接或文件名猜测完整性。

### 3. 配置凭据

`.env` 文件包含以下配置。文档只保留占位符，不记录真实凭据：

```env
# 应用凭据
APP_ID=<your-app-id>
API_KEY=<your-api-key>
API_SECRET=<your-full-api-secret>

# 场景配置
SCENE_ID=<published-scene-id>
AVATAR_ID=<authorized-avatar-id>
VCN=<authorized-vcn>

# WebSocket URL
WS_URL=<avatar-websocket-url>
```

### 4. 启动服务

```bash
npm start
```

服务启动后：
- 访问地址：http://localhost:3000
- 配置接口：http://localhost:3000/api/config
- 签名接口：http://localhost:3000/api/avatar-auth

## 使用说明

### 初始化

1. 打开浏览器访问 http://localhost:3000
2. 点击 "🚀 初始化虚拟人" 按钮
3. 等待连接成功，虚拟人出现

### 文字对话

在文本框输入内容，点击"发送"或按回车，虚拟人会回复并播报。

### 语音交互

1. 点击 "🎤 开始语音" 按钮
2. 允许浏览器使用麦克风
3. 开始说话
4. 点击 "🔴 停止录音" 结束
5. 虚拟人会识别语音并回复

### 动作控制

点击动作按钮（点头、挥手、思考、微笑）触发虚拟人动作。

## 技术要点

### 字段配置（严格遵循 Playbook）

`app.js` 中的 `setGlobalParams` 严格按照 Playbook §3 字段锁定表配置：

```javascript
avatar.setGlobalParams({
  stream: {
    protocol: 'xrtc',
    fps: 25,
    bitrate: 2000,
  },
  avatar: {
    avatar_id: config.avatarId,
    width: 720,
    height: 1280,
    // ✅ 关键：手写 avatar.stream，值原样发送
    stream: {
      protocol: 'xrtc',
      fps: 25,
      bitrate: 2000,    // 单位 kbps，平台实际收到的值
      alpha: 1,         // 1=透明背景
    },
  },
  tts: {
    vcn: config.vcn,
    speed: 50,
    pitch: 50,
    volume: 50,
  },
  avatar_dispatch: {
    interactive_mode: 0,
  },
});
```

### 安全架构

- ✅ `apiSecret` 只存在服务端 `.env`
- ✅ 前端通过 `/api/avatar-auth` 获取 `signedUrl`
- ✅ 服务端 HMAC-SHA256 签名
- ✅ `.env` 在 `.gitignore` 中，不提交到版本控制

### 浏览器自动播放限制

监听 `PlayerEvents.playNotAllowed` 事件，引导用户点击恢复播放：

```javascript
avatar.on(PlayerEvents.playNotAllowed, () => {
  showResumeHint();  // 显示"点击恢复播放"按钮
});
```

## 故障排查

### 错误码速查

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 10110 | 应用配置错误 | 检查 APP_ID |
| 10113 | 认证失败 | 检查 API_KEY/API_SECRET |
| 10120 | 形象未授权 | avatarId 未授权给该 appId |
| 10121 | sceneId 未发布 | 控制台发布场景 |
| 11203 | 并发路数超限 | 上一会话未 destroy |

### 常见问题

**Q: SDK 加载失败？**
A: 对照 `.runtime/sdk-artifact.json` 检查入口路径和 SHA-256，再运行 SDK artifact gate

**Q: 连接失败？**
A: 检查 `.env` 中的凭据是否正确

**Q: 黑屏或无画面？**
A: 检查 AVATAR_ID 是否已授权给该应用

**Q: bitrate 报错 "must be ≥ 200"？**
A: 已按 Playbook 配置，使用手写 `avatar.stream.bitrate: 2000`

## 配置页面

场景配置页面地址以当前账号控制台和 `.env` 中的 appId/sceneId 为准。

可以在控制台修改：
- 形象和发音人
- NLP 模型配置
- 知识库绑定
- 其他高级设置

## 相关链接

- 控制台：https://virtual-man.xfyun.cn/console/
- SDK 文档：查看 SDK 包内的文档

## 当前验证状态

- SDK 入口、类型定义、凭据形态、真实 API、签名、Node 语法、服务启动和两个后端接口已通过静态门禁。
- `connected`、`stream_start`、首帧和文字交互尚无浏览器证据。
- 当前状态为 `needs_runtime_verification`，不是已完成交付。

## 许可证

MIT
