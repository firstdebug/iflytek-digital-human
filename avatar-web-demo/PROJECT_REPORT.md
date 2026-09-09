# Web SDK 项目验证状态

## 项目信息

**项目名称**: avatar-web-demo
**平台**: Web（浏览器）
**交付模式**: Quick（快速模式）
**项目路径**: 当前目录

## 应用配置

- **App/Scene/Avatar/VCN**: 保存在 `.env`，本文档不记录真实值
- **协议**: XRTC（支持透明背景）

## 已实现功能

✅ **文字对话** - 用户通过文字输入与虚拟人对话
✅ **语音交互** - 点击开始/停止模式的语音对话
✅ **动作控制** - 控制虚拟人做出特定动作
✅ **透明背景** - 使用 XRTC 协议，alpha=1

## 项目结构

```
avatar-web-demo/
├── server.js          ✅ Node.js 后端（HMAC-SHA256 签名）
├── package.json       ✅ 项目配置（type: module）
├── .env               ✅ 凭据配置（6 项完整）
├── .gitignore         ✅ 排除敏感文件
├── README.md          ✅ 完整使用说明
├── node_modules/      ✅ 依赖已安装（express, dotenv）
├── public/
│   ├── index.html     ✅ 前端页面（响应式布局）
│   ├── app.js         ✅ SDK 集成（严格遵循 Playbook §3）
│   └── style.css      ✅ 现代化样式
└── sdk/               ✅ SDK 入口与类型定义已校验并记录 SHA-256
```

## Playbook 合规性

### ✅ 架构安全（§1）
- 采用 Node 后端 + 静态前端架构
- apiSecret 只存在服务端 .env
- 前端通过 /api/avatar-auth 获取 signedUrl
- .env 在 .gitignore 中

### ✅ 字段锁定表（§3）
严格按照 Playbook §3 配置 setGlobalParams：

```javascript
stream: {
  protocol: 'xrtc',
  fps: 25,
  bitrate: 2000,
}
avatar: {
  avatar_id: config.avatarId,
  width: 720,
  height: 1280,
  stream: {              // ✅ 手写 avatar.stream（WYSIWYG）
    protocol: 'xrtc',
    fps: 25,
    bitrate: 2000,       // 实际发送值，不再 /1024
    alpha: 1,            // 透明背景
  },
}
```

### ✅ 初始化顺序（§4）
1. new AvatarPlatform()
2. setApiInfo({ signedUrl, appId, sceneId })
3. setGlobalParams({...})
4. avatar.on(事件监听)
5. await avatar.start({ wrapper })

### ✅ 必须监听的事件
- SDKEvents.connected
- SDKEvents.disconnected
- SDKEvents.error
- SDKEvents.stream_start
- PlayerEvents.playNotAllowed（处理自动播放限制）

## 验证结果

### ✅ 后端验证
- [x] node server.js 启动成功
- [x] /api/config 返回完整配置
- [x] /api/avatar-auth 可生成 signedUrl
- [x] .env 中 apiSecret 未暴露

### ✅ SDK 依赖
- [x] SDK 入口：`sdk/avatar-web-sdk/avatar-sdk-web_3.2.3.1002/esm/index.js`
- [x] `.runtime/sdk-artifact.json` 已记录相对路径和 SHA-256

### ⚠️ 端到端验证（尚未完成）
- [ ] 浏览器访问 localhost:3000
- [ ] 点击初始化 → 收到 connected
- [ ] 收到 stream_start（云端推流）
- [ ] 播放器首帧渲染
- [ ] 文本驱动正常
- [ ] 语音交互正常
- [ ] 动作控制正常
- [ ] 透明背景生效

## 下一步操作

### 1. 启动项目

```bash
cd avatar-web-demo
npm start
```

### 2. 浏览器测试

访问 http://localhost:3000

1. 点击 "🚀 初始化虚拟人"
2. 允许麦克风权限（语音功能需要）
3. 测试文字对话
4. 测试语音交互
5. 测试动作控制

## 配置页面

场景配置地址以当前账号控制台和 `.env` 中的 appId/sceneId 为准。

可以修改：
- 形象和发音人
- NLP 模型配置
- 知识库绑定

## 技术亮点

1. **安全架构** - 服务端签名，前端零暴露
2. **字段精确** - 严格遵循 Playbook，避免 bitrate/1024 陷阱
3. **功能完整** - 文字、语音、动作、透明背景四大功能
4. **用户体验** - 响应式布局、状态提示、对话记录
5. **代码质量** - ES Module、清晰注释、错误处理

## 已知限制

1. 浏览器连接、推流、首帧和目标交互证据尚未生成
2. 需 HTTPS 或 localhost（麦克风权限要求）
3. 透明背景需支持 XRTC 的浏览器

## 故障排查

错误码速查已写入 README.md，常见问题包括：
- 10113: 认证失败 → 检查凭据
- 10120: 形象未授权 → 已自动授权
- 10121: 场景未发布 → 已自动发布

## 交付物清单

✅ 完整的 Web 工程（7 个文件）
✅ 场景配置已写入本地环境文件
✅ 形象和发音人已授权
✅ 服务器验证通过
✅ README 和使用说明完整

⚠️ **当前状态**: `needs_runtime_verification`。静态门禁通过，但缺少 `connected`、`stream_start`、首帧和文字交互的浏览器证据，不能标记完成。
