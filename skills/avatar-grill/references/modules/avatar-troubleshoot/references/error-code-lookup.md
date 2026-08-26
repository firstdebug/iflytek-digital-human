# Step 2: 错误码查询

## 2.1 加载错误码库

```javascript
// 从插件根目录的 config/error-codes.yaml 加载
const errorDB = loadYaml('config/error-codes.yaml');

function lookupError(code) {
  const error = errorDB.errors[code];
  
  if (!error) {
    return {
      found: false,
      suggestion: "未知错误码，请提供完整日志进行分析"
    };
  }
  
  return {
    found: true,
    category: error.category,
    severity: error.severity,
    message: error.message,
    cause: error.cause,
    fix: error.fix,
    docs: error.docs,
    platform_specific: error.platforms || {}
  };
}
```

## 2.2 错误码匹配示例

**示例 1: 10113 - apiSecret 错误**
```yaml
error_code: "10113"
category: "authentication"
severity: "critical"
message: "apiSecret 错误或签名生成有误"

cause:
  - "apiSecret 复制错误"
  - "签名算法实现不正确"
  - "时间戳偏差过大"
  - "URL 编码问题"

fix:
  - "重新复制 apiSecret，确保完整无误"
  - "检查签名生成流程: HMAC-SHA256 → Base64"
  - "确认 date 使用 UTC 时区 GMT 格式"
  - "检查 authorization 参数是否正确 URL 编码"

code_example: |
  const origin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
  const signature = hmacSha256(apiSecret, origin);
  const authorization = `api_key="${apiKey}", algorithm="hmac-sha256", ...`;
```

**直接输出修复建议**:
```
诊断结果: apiSecret 错误或签名生成有误

可能原因:
1. apiSecret 复制时包含空格或换行
2. 签名算法实现错误
3. date 格式不正确（需要 UTC GMT 格式）
4. authorization 参数未正确 URL 编码

修复步骤:
1. 检查 apiSecret
   - 重新从控制台复制
   - 确保无多余空格
   - 验证长度（通常 32 位）

2. 检查签名生成（以 Web 为例）:
   const origin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
   const signature = CryptoJS.HmacSHA256(origin, apiSecret).toString(CryptoJS.enc.Base64);
   
3. 检查 date 格式:
   const date = new Date().toUTCString();
   // 正确格式: "Mon, 13 Jul 2026 10:30:00 GMT"

验证: 修复后重新连接，应收到 avatar_ready 事件
```
