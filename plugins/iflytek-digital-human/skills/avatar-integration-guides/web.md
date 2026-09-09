---
name: web-integration-guide
description: Web 平台虚拟人 SDK 快速集成指南
platform: web
---

# Web 平台虚拟人 SDK 集成指南

> **⚠️ 生产/自建工程请以 Playbook 为准**：本指南是"五分钟快速理解"用的最小示例。
> **真正构建可交付的 Web SDK 工程时，必须遵循**
> `avatar-executing/references/web-sdk-build-playbook.md`（HARD-GATE）——
> 它规定了安全架构（后端签名，不在前端硬编码 apiSecret）、字段锁定表、以及
> **bitrate 会被 SDK /1024** 的关键陷阱。仅照本页最小示例可能踩 bitrate/protocol 报错。

## 五分钟快速接入

### Step 1: 准备工作

**获取凭据** (从虚拟人交互平台):
```
appId: 你的应用ID
apiKey: API密钥
apiSecret: API密钥对
sceneId: 接口服务ID
avatarId: 形象ID
vcn: 发音人ID
```

**下载 SDK**:
- 下载 avatar-sdk-web_3.2.3.1002.zip
- 解压到项目目录 `src/sdk/`

---

### Step 2: 基础集成

**HTML 结构**:
```html
<!DOCTYPE html>
<html>
<head>
  <title>虚拟人 Demo</title>
  <style>
    .avatar-container {
      width: 720px;
      height: 1280px;
      background: #000;
    }
  </style>
</head>
<body>
  <div class="avatar-container"></div>
  <button id="start-btn">启动虚拟人</button>
  <button id="speak-btn">说话</button>
  
  <script type="module" src="./app.js"></script>
</body>
</html>
```

**JavaScript 代码** (`app.js`):
```javascript
import AvatarPlatform, { SDKEvents, PlayerEvents } from './sdk/avatar-sdk-web_3.2.3.1002/index.js';

// 1. 创建实例
const avatar = new AvatarPlatform();

// 2. 配置凭据
avatar.setApiInfo({
  serverUrl: 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
  appId: 'your_app_id',
  apiKey: 'your_api_key',
  apiSecret: 'your_api_secret',
  sceneId: 'your_scene_id'
});

// 3. 配置全局参数
// 关键：手写 avatar.stream，其 bitrate【原样发送】不会被 SDK /1024（所见即所发）。
// 若只配顶层 stream.bitrate:2000，SDK 会发送 floor(2000/1024)=1，触发 "must be >= 200" 报错。
// 详见 avatar-executing/references/web-sdk-build-playbook.md §0/§3。
avatar.setGlobalParams({
  stream: { 
    protocol: 'xrtc',
    fps: 25,
    bitrate: 2000      // ⚠️ 顶层此值会被 SDK /1024，仅占位；真实值看下面 avatar.stream
  },
  avatar: { 
    avatar_id: 'your_avatar_id',
    width: 720,
    height: 1280,
    stream: {
      protocol: 'xrtc',  // 必填
      fps: 25,           // 必填
      bitrate: 2000,     // 必填，单位 kbps，[200,20000]，平台实际收到此值
      alpha: 0           // 必填，0=不透明 1=透明背景(仅xrtc)
    }
  },
  tts: { 
    vcn: 'your_vcn',
    speed: 50,
    pitch: 50,
    volume: 50
  }
});

// 4. 事件监听
avatar
  .on(SDKEvents.connected, () => {
    console.log('连接成功');
  })
  .on(SDKEvents.error, (e) => {
    console.error('错误:', e?.code, e?.message);
  })
  .on(SDKEvents.frame_start, (data) => {
    console.log('开始播报');
  });

// 5. 处理浏览器自动播放限制
const player = avatar.player;
player.on(PlayerEvents.playNotAllowed, () => {
  console.log('需要用户交互才能播放');
  document.addEventListener('click', () => {
    player.resume();
  }, { once: true });
});

// 6. 启动虚拟人
document.getElementById('start-btn').onclick = async () => {
  try {
    await avatar.start({ 
      wrapper: document.querySelector('.avatar-container') 
    });
    console.log('虚拟人启动成功');
  } catch (err) {
    console.error('启动失败:', err);
  }
};

// 7. 文本驱动
document.getElementById('speak-btn').onclick = async () => {
  await avatar.writeText('你好，欢迎使用虚拟人服务', { nlp: false });
};
```

---

### Step 3: 本地运行

**使用静态服务器**:
```bash
# 方式 1: npx serve
npx serve . -p 8080

# 方式 2: Python
python -m http.server 8080

# 方式 3: PHP
php -S localhost:8080
```

**打开浏览器**: `http://localhost:8080`

---

## 常见功能扩展

### 语音交互

```javascript
// 创建录音器
const recorder = avatar.createRecorder({ sampleRate: 16000 });

// 监听识别结果
avatar.on(SDKEvents.asr, (data) => {
  console.log('识别:', data.text);
});

avatar.on(SDKEvents.nlp, (data) => {
  console.log('回复:', data.answer);
});

// 按住说话
document.getElementById('record-btn').addEventListener('mousedown', () => {
  recorder.startRecord(60 * 1000, null, { nlp: true });
});

document.getElementById('record-btn').addEventListener('mouseup', () => {
  recorder.stopRecord();
});
```

### 透明背景

```javascript
// 全局参数 - 注意 avatar.stream 也必须配置
avatar.setGlobalParams({
  stream: { 
    protocol: 'xrtc',  // 必须 XRTC
    fps: 25,
    bitrate: 2000,
    alpha: 1           // 透明背景
  },
  avatar: {
    avatar_id: 'your_avatar_id',
    width: 720,
    height: 1280,
    stream: {
      protocol: 'xrtc',
      fps: 25,
      bitrate: 2000,
      alpha: 1         // avatar.stream.alpha 也必须设为 1
    }
  },
  tts: { vcn: 'your_vcn', speed: 50, pitch: 50, volume: 50 }
});

// 播放器配置
avatar.player.alpha = true;
```

---

## 生产环境部署

### 1. HTTPS 配置

**必需**: 录音功能需要 HTTPS 或 localhost

**使用 Nginx**:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        root /var/www/html;
        index index.html;
    }
}
```

### 2. 安全配置

**不要在前端硬编码 apiSecret**:
```javascript
// ❌ 错误: 明文暴露
const apiSecret = 'your_api_secret';

// ✓ 正确: 从环境变量或后端获取
const apiSecret = import.meta.env.VITE_AVATAR_API_SECRET;

// ✓ 更好: 后端签名，前端只传 signedUrl
avatar.setApiInfo({
  appId: 'xxx',
  sceneId: 'xxx',
  signedUrl: await fetch('/api/avatar-auth').then(r => r.json()).url
});
```

### 3. 错误处理

```javascript
avatar.on(SDKEvents.error, (e) => {
  switch(e?.code) {
    case '10110':
      showError('应用配置错误，请联系管理员');
      break;
    case '10113':
      showError('认证失败，请重试');
      break;
    case '10120':
      showError('形象未授权，请联系管理员');
      break;
    default:
      showError('连接失败，请检查网络');
  }
});
```

---

## 故障排查

### 黑屏无视频
1. 检查控制台是否有错误码
2. 确认收到 `stream_start` 事件
3. 检查 avatarId 是否已授权
4. 检查播放器分包是否加载

### 无声音
1. 检查是否收到 `playNotAllowed` 事件
2. 引导用户点击页面后调用 `player.resume()`
3. 检查系统音量和浏览器静音设置

### 连接失败
1. 检查 appId/apiKey/apiSecret 拼写
2. 检查 sceneId 是否已发布
3. 检查网络和防火墙
4. 查看完整错误码

---

## 完整示例

查看 `examples/web/` 目录下的完整示例代码。

## API 文档

详细 API 文档: https://doc.xfyun.cn/avatar/web-sdk

## 技术支持

- 文档: https://doc.xfyun.cn/avatar
- 控制台: https://virtual-man.xfyun.cn
- 联系支持团队
