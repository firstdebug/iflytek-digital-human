# Step 3: 鉴权握手验证

## 3.1 签名生成验证

**检查签名算法实现**:
```javascript
// 正确的签名流程（Web）
const crypto = require('crypto');

function generateSignature(apiKey, apiSecret, host, path, date) {
  // 1. 构造签名原文
  const origin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
  console.log('签名原文:', origin);
  
  // 2. HMAC-SHA256 签名
  const signature = crypto
    .createHmac('sha256', apiSecret)
    .update(origin)
    .digest('base64');
  console.log('签名:', signature);
  
  // 3. 构造 authorization
  const authorization = [
    `api_key="${apiKey}"`,
    `algorithm="hmac-sha256"`,
    `headers="host date request-line"`,
    `signature="${signature}"`
  ].join(', ');
  console.log('Authorization:', authorization);
  
  // 4. Base64 编码
  const authBase64 = Buffer.from(authorization).toString('base64');
  console.log('Authorization (Base64):', authBase64);
  
  return authBase64;
}

// 验证示例
const host = 'avatar.cn-huadong-1.xf-yun.com';
const path = '/v1/interact';
const date = new Date().toUTCString();  // 必须 UTC GMT 格式

const authBase64 = generateSignature(apiKey, apiSecret, host, path, date);
```

**常见签名错误**:
```yaml
错误 1: date 格式不正确
  ❌ 错误: "2026-07-13 10:30:00"
  ✓ 正确: "Mon, 13 Jul 2026 10:30:00 GMT"
  fix: "使用 toUTCString() 或等效方法"

错误 2: signature 算法错误
  ❌ 错误: "HMAC-SHA1 或 MD5"
  ✓ 正确: "HMAC-SHA256"
  fix: "使用 crypto.createHmac('sha256', ...)"

错误 3: authorization 参数顺序或格式错误
  ❌ 错误: 'api_key=xxx,algorithm=hmac-sha256'
  ✓ 正确: 'api_key="xxx", algorithm="hmac-sha256"'
  fix: "注意引号和逗号分隔"

错误 4: Base64 编码错误
  ❌ 错误: "URL 编码或其他编码"
  ✓ 正确: "标准 Base64 编码"
  fix: "使用 btoa() 或 Buffer.toString('base64')"
```

## 3.2 鉴权参数验证

**检查 URL 参数**:
```javascript
const url = new URL('wss://avatar.cn-huadong-1.xf-yun.com/v1/interact');

// 必需参数
url.searchParams.set('authorization', authBase64);
url.searchParams.set('host', host);
url.searchParams.set('date', date);

console.log('完整 URL:', url.toString());

// 验证参数是否正确编码
console.log('authorization 编码:', 
  url.searchParams.get('authorization') === authBase64);
```

**URL 编码问题**:
```yaml
问题: "authorization 参数包含 + 或 / 被错误编码"
解决: "使用 encodeURIComponent() 正确编码"

问题: "date 参数中的逗号和空格被编码"
解决: "date 需要编码，但 authorization 已经是 Base64 无需再编码"
```
