# Layer 5: 配置参数验证（核心）

## 已知配置陷阱

### 1. bitrate 参数错误 ⭐⭐⭐

**错误信息**:
```
$.parameter.avatar.stream.bitrate' value must be larger or equal than 200
```

**原因**: SDK 要求 `bitrate >= 200`

**检测**:
```javascript
function checkBitrateConfig(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  
  // 检查 bitrate 配置
  const bitrateMatch = content.match(/bitrate:\s*(\d+)/);
  
  if (bitrateMatch) {
    const bitrate = parseInt(bitrateMatch[1]);
    
    if (bitrate < 200) {
      return {
        valid: false,
        error: `bitrate 值 ${bitrate} 小于最小要求 200`,
        fix: '修改为 2000'
      };
    }
  }
  
  return { valid: true };
}
```

**自动修复**:
```javascript
function fixBitrateConfig(filePath) {
  let content = fs.readFileSync(filePath, 'utf-8');
  
  // 修复 bitrate 配置
  content = content.replace(
    /bitrate:\s*(\d+)/,
    (match, value) => {
      const bitrate = parseInt(value);
      if (bitrate < 200) {
        console.log(`⚠️  修复 bitrate: ${bitrate} → 2000`);
        return 'bitrate: 2000';
      }
      return match;
    }
  );
  
  fs.writeFileSync(filePath, content);
  return true;
}
```

### 2. SDK 路径错误

**错误信息**:
```
SDK 加载失败: 请确认 SDK 已下载到 /sdk/ 目录
```

**检测**:
```javascript
function checkSDKPath(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  
  // 检查 SDK import 路径
  const sdkPathMatch = content.match(/\/sdk\/avatar-sdk-web_[\d.]+\/([\w/]+\.js)/);
  
  if (sdkPathMatch) {
    const sdkPath = sdkPathMatch[0];
    const fullPath = path.join(process.cwd(), 'public', sdkPath);
    
    if (!fs.existsSync(fullPath)) {
      // 尝试常见路径
      const commonPaths = [
        '/sdk/avatar-sdk-web_3.2.3.1002/esm/index.js',
        '/sdk/avatar-sdk-web_3.2.3.1002/index.js'
      ];
      
      for (const testPath of commonPaths) {
        if (fs.existsSync(path.join(process.cwd(), 'public', testPath))) {
          return {
            valid: false,
            error: `SDK 路径错误: ${sdkPath}`,
            fix: `应该使用: ${testPath}`
          };
        }
      }
    }
  }
  
  return { valid: true };
}
```

### 3. 凭据未正确加载

**检测**:
```javascript
function checkEnvLoading(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  
  // 检查是否正确使用 import.meta.env
  if (!content.includes('import.meta.env.VITE_')) {
    return {
      valid: false,
      error: '凭据加载方式错误',
      fix: '应使用 import.meta.env.VITE_AVATAR_*'
    };
  }
  
  return { valid: true };
}
```

### 4. 事件监听不完整

**检测**:
```javascript
function checkEventListeners(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  
  const requiredEvents = [
    'connected',
    'error',
    'disconnected'
  ];
  
  const missing = requiredEvents.filter(event => 
    !content.includes(`SDKEvents.${event}`)
  );
  
  if (missing.length > 0) {
    return {
      valid: false,
      error: `缺少关键事件监听: ${missing.join(', ')}`,
      fix: '添加事件监听'
    };
  }
  
  return { valid: true };
}
```
