# Web 平台工具链检查

Web 分支的检查项清单、检测实现、修复模板、编排流程与状态分类、输出格式。
骨架与 `summarizeStatus` 通用实现见 `../SKILL.md`；本文件只承载 Web 特定载荷。

---

## 检查项清单

| # | 检查项 | 必需性 | 重要性 | 说明 |
|---|--------|--------|--------|------|
| 1 | Node.js 环境 | 可选 | Medium | 纯静态页面不需要 |
| 2 | 包管理器 (npm/yarn/pnpm) | 可选 | Low | 非 Node.js 项目可忽略 |
| 3 | 构建工具 (Vite/Webpack/Rollup/Vue CLI) | 可选 | Low | 读取项目配置文件识别 |
| 4 | HTTPS 环境 | 条件必需 | ⭐⭐⭐ | 录音功能必需 |
| 5 | ESM 支持 | 必需 | ⭐⭐⭐ | SDK 为 ESM 格式 |
| 6 | 浏览器兼容性 | 运行时 | ⭐⭐ | 只能在浏览器运行时检测 |
| 7 | 静态服务器 | 条件 | Low | 无构建工具时检查 |

检查优先级：HTTPS（录音时）> ESM 支持 > Node.js 版本 > 构建工具。
灵活性边界：纯静态页面不需要 Node.js；不使用录音功能可跳过 HTTPS；多种 ESM 配置方式均可接受。

---

## 1. Node.js 环境（可选）

**检查条件**: 项目使用构建工具或本地开发服务器

**检查方法**:
```bash
node --version
```

**要求**:
```yaml
required: false  # 纯静态页面不需要
recommended_version: ">=14.0.0"
optimal_version: ">=18.0.0"
```

**判断**:
```javascript
const nodeVersion = execSync('node --version').toString().trim();
const major = parseInt(nodeVersion.match(/v(\d+)/)[1]);

if (major >= 18) {
  return { status: 'optimal', version: nodeVersion };
} else if (major >= 14) {
  return { status: 'acceptable', version: nodeVersion, 
           note: '建议升级到 Node.js 18+' };
} else if (major < 14) {
  return { status: 'outdated', version: nodeVersion,
           fix: '请升级到 Node.js 14+ 或使用纯静态服务' };
} else {
  return { status: 'not_found', 
           fix: '安装 Node.js 或使用 Python/PHP 静态服务' };
}
```

---

## 2. 包管理器（可选）

**检查方法**:
```bash
npm --version
yarn --version
pnpm --version
```

**判断**:
```javascript
const managers = [];
if (hasCommand('npm')) managers.push('npm');
if (hasCommand('yarn')) managers.push('yarn');
if (hasCommand('pnpm')) managers.push('pnpm');

if (managers.length > 0) {
  return { status: 'available', managers };
} else {
  return { status: 'not_found', 
           note: '非 Node.js 项目可忽略' };
}
```

---

## 3. 构建工具检查

**检查方法**: 读取项目配置文件

```javascript
const buildTools = [];

if (fs.existsSync('vite.config.js') || fs.existsSync('vite.config.ts')) {
  buildTools.push({ name: 'Vite', config: 'vite.config.js' });
}

if (fs.existsSync('webpack.config.js')) {
  buildTools.push({ name: 'Webpack', config: 'webpack.config.js' });
}

if (fs.existsSync('rollup.config.js')) {
  buildTools.push({ name: 'Rollup', config: 'rollup.config.js' });
}

if (fs.existsSync('vue.config.js')) {
  buildTools.push({ name: 'Vue CLI', config: 'vue.config.js' });
}

return { buildTools };
```

---

## 4. HTTPS 环境检查

**重要性**: ⭐⭐⭐ 录音功能必需

**检查方法**: 读取开发服务器配置

```javascript
// Vite
if (fs.existsSync('vite.config.js')) {
  const config = require('./vite.config.js');
  const httpsEnabled = config.server?.https || false;
  const host = config.server?.host || 'localhost';
  
  if (httpsEnabled) {
    return { status: 'https_enabled', server: 'vite' };
  } else if (host === 'localhost' || host === '127.0.0.1') {
    return { status: 'localhost_ok', 
             note: 'localhost 环境可使用麦克风' };
  } else {
    return { status: 'needs_https',
             fix: '录音功能需要 HTTPS 或 localhost 环境' };
  }
}

// Webpack Dev Server
if (fs.existsSync('webpack.config.js')) {
  // 类似检查...
}

// 无构建工具
return { status: 'manual_check_needed',
         note: '请确保生产环境为 HTTPS' };
```

**修复建议**:
```javascript
if (needsHttps) {
  console.log(`
配置 HTTPS 开发环境:

方案 1: Vite (推荐)
  npm install -D @vitejs/plugin-basic-ssl
  
  // vite.config.js
  import basicSsl from '@vitejs/plugin-basic-ssl'
  export default {
    plugins: [basicSsl()],
    server: { https: true }
  }

方案 2: mkcert (通用)
  # 安装 mkcert
  brew install mkcert  # macOS
  choco install mkcert # Windows
  
  # 生成本地证书
  mkcert -install
  mkcert localhost
  
  # 使用生成的证书启动服务

方案 3: 使用 localhost
  # 如果只在本地测试，使用 localhost 即可
  npm run dev -- --host localhost
  `);
}
```

---

## 5. ESM 支持检查

**重要性**: ⭐⭐⭐ SDK 为 ESM 格式

**检查方法**:
```javascript
// 方式 1: package.json type 字段
if (fs.existsSync('package.json')) {
  const pkg = require('./package.json');
  if (pkg.type === 'module') {
    return { status: 'esm_enabled', method: 'package.json' };
  }
}

// 方式 2: 使用构建工具
if (hasBuildTool(['vite', 'webpack', 'rollup'])) {
  return { status: 'esm_supported', method: 'build_tool' };
}

// 方式 3: HTML 中使用 type="module"
const htmlFiles = glob.sync('**/*.html');
for (const file of htmlFiles) {
  const content = fs.readFileSync(file, 'utf-8');
  if (content.includes('type="module"')) {
    return { status: 'esm_supported', method: 'script_tag' };
  }
}

return { status: 'esm_not_configured',
         fix: '需要配置 ESM 支持' };
```

**修复建议**:
```javascript
if (!esmSupported) {
  console.log(`
配置 ESM 支持:

方案 1: package.json (纯 Node.js 项目)
  {
    "type": "module"
  }

方案 2: HTML script 标签
  <script type="module" src="./app.js"></script>

方案 3: 使用构建工具
  Vite / Webpack / Rollup 原生支持 ESM

方案 4: 静态服务器
  npx serve . -p 8080
  # 或
  python -m http.server 8080
  `);
}
```

---

## 6. 浏览器兼容性检查（运行时）

**重要性**: ⭐⭐ 影响功能可用性

**检查项**:
```javascript
// 这些检查只能在浏览器运行时进行
const browserChecks = {
  webrtc: 'navigator.mediaDevices',
  websocket: 'WebSocket',
  h264_decode: 'document.createElement("video").canPlayType("video/mp4; codecs=avc1.42E01E")',
  getUserMedia: 'navigator.mediaDevices.getUserMedia'
};

// 提供检测代码片段
return {
  status: 'runtime_check_needed',
  detection_code: `
// 在浏览器控制台运行以下代码:

console.log('WebRTC:', !!navigator.mediaDevices);
console.log('WebSocket:', !!window.WebSocket);
console.log('H.264 解码:', 
  document.createElement('video')
    .canPlayType('video/mp4; codecs="avc1.42E01E"'));
console.log('getUserMedia:', 
  !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));

// 推荐浏览器: Chrome/Edge >= 80, Firefox >= 75, Safari >= 13
  `
};
```

---

## 7. 静态服务器可用性（无构建工具时）

**检查方法**:
```bash
# 检查常见静态服务器命令
which serve
which http-server
python --version
php --version
```

**判断**:
```javascript
const servers = [];

if (hasCommand('serve')) {
  servers.push({ name: 'serve', 
                 command: 'npx serve . -p 8080' });
}

if (hasCommand('http-server')) {
  servers.push({ name: 'http-server', 
                 command: 'npx http-server -p 8080' });
}

if (hasCommand('python')) {
  servers.push({ name: 'Python', 
                 command: 'python -m http.server 8080' });
}

if (hasCommand('php')) {
  servers.push({ name: 'PHP', 
                 command: 'php -S localhost:8080' });
}

if (servers.length > 0) {
  return { status: 'servers_available', servers };
} else {
  return { status: 'no_server_found',
           fix: '安装 Node.js 后使用 npx serve' };
}
```

---

## 完整检查流程（编排）

```javascript
async function checkWebToolchain() {
  const results = {
    platform: 'web',
    checks: {}
  };
  
  // 1. Node.js（可选）
  results.checks.nodejs = await checkNodeJS();
  
  // 2. 包管理器（可选）
  results.checks.package_manager = await checkPackageManager();
  
  // 3. 构建工具
  results.checks.build_tool = await checkBuildTool();
  
  // 4. HTTPS 环境
  results.checks.https = await checkHTTPS();
  
  // 5. ESM 支持
  results.checks.esm = await checkESM();
  
  // 6. 浏览器兼容性（运行时检查）
  results.checks.browser = provideBrowserCheckCode();
  
  // 7. 静态服务器（无构建工具时）
  if (!results.checks.build_tool.found) {
    results.checks.static_server = await checkStaticServer();
  }
  
  // 汇总状态（summarizeStatus 通用骨架见 ../SKILL.md）
  results.status = summarizeStatus(results.checks);
  
  return results;
}
```

## 状态分类（填入通用 summarizeStatus）

Web 分支在通用 `summarizeStatus` 骨架的「平台特定分类规则」处填入：

```javascript
// HTTPS 检查（录音功能时为 critical）
if (needsRecording && checks.https.status === 'needs_https') {
  critical.push('HTTPS 环境缺失（录音功能必需）');
}

// ESM 检查
if (checks.esm.status === 'esm_not_configured') {
  warnings.push('ESM 未配置');
}

// Node.js 版本过低
if (checks.nodejs.status === 'outdated') {
  warnings.push('Node.js 版本过低');
}
```

---

## 输出格式

### 成功输出
```yaml
status: "all_ok"
platform: "web"
checks:
  nodejs:
    status: "optimal"
    version: "v18.16.0"
  build_tool:
    found: true
    name: "Vite"
  https:
    status: "https_enabled"
  esm:
    status: "esm_supported"
    method: "build_tool"
  static_server:
    not_needed: true
```

### 警告输出
```yaml
status: "warnings"
issues:
  - "Node.js 版本过低，建议升级到 18+"
  - "ESM 未配置，需要添加 type=\"module\""
checks:
  nodejs:
    status: "acceptable"
    version: "v14.17.0"
    recommendation: "升级到 Node.js 18+"
  esm:
    status: "esm_not_configured"
    fix: "在 HTML 中使用 <script type=\"module\"> 或配置构建工具"
```

### 关键问题输出
```yaml
status: "critical_issues"
issues:
  - "HTTPS 环境缺失（录音功能必需）"
checks:
  https:
    status: "needs_https"
    fix: |
      配置 HTTPS 开发环境:
      1. 使用 Vite + @vitejs/plugin-basic-ssl
      2. 使用 mkcert 生成本地证书
      3. 或在 localhost 环境下运行
```
