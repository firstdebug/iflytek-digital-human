# 集成逻辑与调用示例

## 检测 SDK 状态

```javascript
function detectSDK(platform) {
  const paths = {
    web: './sdk/avatar-sdk-web_*/index.js',
    android: 'app/libs/avatar-core-*.aar',
    ios: 'Frameworks/AvatarSDK.framework'
  };
  
  const found = glob(paths[platform]);
  
  if (found.length > 0) {
    console.log('✅ SDK 已存在:', found[0]);
    return { status: 'found', path: found[0] };
  }
  
  console.log('❌ SDK 未找到，准备下载');
  return { status: 'missing' };
}
```

## 在 Claude 中调用（自动执行下载）

```javascript
// 在 avatar-preflight Layer 3 检测到 SDK 缺失时
async function downloadSDK(platform) {
  console.log('📥 开始自动下载 SDK...');
  
  // 1. 确定平台
  if (platform === 'web') {
    // 2. 执行下载脚本
    const script = platform === 'win32' 
      ? 'download-sdk.ps1'  // Windows
      : 'download-sdk.sh';  // macOS/Linux
    
    // 3. 运行脚本
    await Bash(`bash ${script}`);
    
    // 4. 验证下载结果
    const sdkPath = glob('./sdk/avatar-sdk-web_*/index.js');
    
    if (sdkPath.length > 0) {
      console.log('✅ SDK 下载成功:', sdkPath[0]);
      return { status: 'success', path: sdkPath[0] };
    } else {
      console.log('❌ SDK 下载失败');
      return { status: 'failed' };
    }
  }
}
```

## 集成到 preflight

```yaml
# avatar-preflight Layer 3: SDK 下载

Step 1: 检测 SDK
  → 调用 detectSDK(platform)

Step 2: 如果缺失
  → 提示: "SDK 未找到，正在自动下载..."
  → 调用 avatar-artifact-download
  → 执行下载脚本

Step 3: 验证下载结果
  → 如果成功: ✅ 继续 Layer 4
  → 如果失败: 
      - 诊断网络问题
      - 提供技术支持联系方式

Step 4: 记录到 dev-env.yaml
  sdk_downloaded: true
  sdk_path: ./sdk/avatar-sdk-web_3.2.3.1002/
  sdk_version: 3.2.3.1002
```

## 凭据辅助检查

```javascript
function checkCredentials() {
  console.log('💡 获取凭据步骤:');
  console.log('1. 登录控制台: https://virtual-man.xfyun.cn');
  console.log('2. 创建应用');
  console.log('3. 获取凭据:');
  console.log('   - appId');
  console.log('   - apiKey');
  console.log('   - apiSecret');
  console.log('4. 创建接口服务，获取 sceneId');
  console.log('5. 授权形象，获取 avatarId 和 vcn');
  
  // 引导用户填写
  const hasCredentials = askUser('是否已获取凭据？');
  
  if (!hasCredentials) {
    console.log('请先登录控制台获取凭据');
    openBrowser('https://virtual-man.xfyun.cn');
    return false;
  }
  
  return true;
}
```

---

## 使用示例

### 场景 1: preflight 自动下载

```
执行: avatar-preflight

Layer 3: SDK 依赖检查
  → ❌ SDK 未找到
  → 📥 正在自动下载...
  → [进度条] ████████████ 100% (5.2 MB)
  → ✅ 下载完成
  → ✅ 解压完成
  → ✅ 验证通过
  → SDK 路径: ./sdk/avatar-sdk-web_3.2.3.1002/
```

### 场景 2: 用户主动请求

```
用户: "帮我下载虚拟人 Web SDK"

执行: avatar-artifact-download
  → 检测平台: Web
  → 开始下载...
  → ✅ 完成
```

### 场景 3: 下载失败，手动备份

```
执行: avatar-artifact-download
  → ❌ 下载失败（网络错误）
  → 💡 备用方案：检查网络连接、防火墙设置
  → 如仍失败，联系技术支持
```

### 场景（代码调用）: preflight 检测到 SDK 缺失

```javascript
// avatar-preflight Layer 3
const sdkStatus = detectSDKStatus('web');

if (sdkStatus.status === 'missing') {
  console.log('SDK 未找到，开始自动下载...');
  await downloadSDK('web', './sdk/');
}
```

### 场景（代码调用）: 用户主动下载

```javascript
// 用户: "帮我下载 Android SDK"
await downloadSDK('android', 'app/libs/');
```
