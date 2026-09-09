# 凭据验证

## 基础凭据格式验证

```javascript
function validateBasicCredentials(appId, apiKey, apiSecret) {
  const errors = [];
  
  // appId: 8 位数字
  if (!/^\d{8}$/.test(appId)) {
    errors.push('appId 格式错误（应为 8 位数字）');
  }
  
  // apiKey: 32 位十六进制
  if (!/^[a-f0-9]{32}$/.test(apiKey)) {
    errors.push('apiKey 格式错误（应为 32 位十六进制）');
  }
  
  // apiSecret: 32 位十六进制
  if (!/^[a-f0-9]{32}$/.test(apiSecret)) {
    errors.push('apiSecret 格式错误（应为 32 位十六进制）');
  }
  
  return {
    valid: errors.length === 0,
    errors: errors
  };
}
```

## 本地格式验证（完整凭据）

```javascript
function validateCredentials(credentials) {
  const { appId, apiKey, apiSecret, sceneId, avatarId, vcn } = credentials;
  
  const checks = [];
  
  // 1. 基础凭据格式
  const basicCheck = validateBasicCredentials(appId, apiKey, apiSecret);
  if (!basicCheck.valid) {
    checks.push(...basicCheck.errors);
  }
  
  // 2. sceneId 格式（通常是 32 位十六进制）
  if (!/^[a-f0-9]{32}$/.test(sceneId)) {
    checks.push('sceneId 格式可能错误');
  }
  
  // 3. avatarId 格式（纯数字或 cnr 开头）
  if (!/^\d+$/.test(avatarId) && !/^cnr/.test(avatarId)) {
    checks.push('avatarId 格式可能错误');
  }
  
  // 4. vcn 不为空
  if (!vcn || vcn.length === 0) {
    checks.push('vcn 未配置');
  }
  
  return {
    valid: checks.length === 0,
    errors: checks
  };
}
```

## 在线连接验证

```javascript
async function verifyCredentialsOnline(credentials) {
  console.log('🔍 验证凭据有效性...');
  
  try {
    // 尝试建立 WebSocket 连接
    const testConnection = await createTestConnection(credentials);
    
    if (testConnection.success) {
      console.log('✅ 凭据验证成功');
      return { valid: true };
    } else {
      return {
        valid: false,
        error: testConnection.error,
        errorCode: testConnection.errorCode
      };
    }
  } catch (error) {
    return {
      valid: false,
      error: error.message
    };
  }
}
```

## 输出格式

### 验证成功
```yaml
status: "valid"
credentials:
  appId: "12345678"
  apiKey: "abcd...f"
  apiSecret: "****"  # 脱敏
  sceneId: "scene..."
  avatarId: "118801001"
  vcn: "x4_yezi"
verified: true
saved: ".env"
```

### 验证失败
```yaml
status: "invalid"
errors:
  - "apiSecret 格式错误"
  - "sceneId 未发布"
fix:
  - "检查 apiSecret 拼写"
  - "在控制台发布接口服务"
```
