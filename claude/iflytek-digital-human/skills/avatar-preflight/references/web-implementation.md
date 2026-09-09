# Layer 3.1: Web 平台 SDK 依赖检查

## Step 3.1.1: SDK 文件检查

**检查项**:
```
必需文件:
  - index.js (SDK 入口)
  - xrtc-player-*.js 或 webrtc-player-*.js (播放器分包)

可选文件:
  - index.d.ts (TypeScript 项目)
```

**检查方式**:
```bash
# 1. 扫描项目中是否已有 SDK
find . -name "index.js" -path "*/avatar-sdk-web*"

# 2. 未找到时询问用户
AskUserQuestion:
  - 选项1: 指定已下载的 SDK 路径
  - 选项2: 自动下载到 ./sdk/avatar-sdk-web_3.2.3.1002/
  - 选项3: 稍后手动配置（跳过）
```

**PASS 标志**: SDK 文件路径明确且可读
**FAIL 处理**: 提供下载链接，询问保存路径

---

## Step 3.1.2: 浏览器环境检查

**检查项**:
```yaml
关键要求:
  1. HTTPS 或 localhost（麦克风权限要求）
  2. ESM 支持（SDK 为 ESM 格式）
  3. WebRTC 支持（navigator.mediaDevices）
```

**检查方式**:
```javascript
// 1. HTTPS 检查
if (devServerConfig) {
  const isHttps = devServerConfig.includes('https') || 
                  devServerConfig.includes('localhost');
  
  if (!isHttps && needsRecording) {
    WARN("录音功能需要 HTTPS 或 localhost");
  }
}

// 2. ESM 检查
if (packageJson.type !== 'module' && !usesViteOrWebpack) {
  WARN("SDK 为 ESM 格式，需配置静态服务器或构建工具");
}

// 3. WebRTC 检查（运行时）
// 仅提示，无法预先检查
INFO("SDK 依赖 WebRTC，请确保目标浏览器支持");
```

**PASS 标志**: 环境配置合理
**FAIL 处理**: 给出配置建议
```
非 HTTPS → 配置本地 HTTPS 服务（mkcert）或使用 localhost
不支持 ESM → 使用 Vite/Webpack 或配置 http-server 等静态服务
```

---

## Web 工具链验证（Layer 5.3）

**调用**: `toolchain`（platform=web，读 references/web-checks.md）

**检查项**:
```bash
# 1. Node.js 版本（如需本地开发服务器）
node --version  # >= 14

# 2. npm/yarn/pnpm 可用
npm --version

# 3. 静态服务器可启动（可选）
npx serve --version
```

**PASS 标志**: 工具链可用（或不需要）
**FAIL 处理**: 
```
Node.js 未安装 → 提供下载链接
版本过低 → 建议升级
不需要工具链 → PASS（纯静态页面）
```

---

## Web 最小验证（Layer 6）

**生成内容**:
```
Web: 
  - index.html (引入 SDK)
  - app.js (初始化 + 连接 + 拉流)
  - 使用真实凭据和最简参数
```

**执行验证**:
```bash
# 启动本地静态服务
npx serve . -p 8080

# 打开浏览器
open http://localhost:8080

# 检查控制台输出（需用户手动确认）
```

**关键事件序列**:
```
1. SDK 初始化成功: AvatarPlatform 创建成功
2. WebSocket 连接成功: 收到 SDKEvents.connected 或类似事件
3. 收到 stream_start: 云端开始推流
4. 播放器首帧渲染: PlayerEvents.play / playing
```
