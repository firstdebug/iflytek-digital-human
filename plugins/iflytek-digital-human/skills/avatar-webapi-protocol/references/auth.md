# 鉴权 URL 生成（HMAC-SHA256）

WebAPI 采用 **HMAC-SHA256** 签名，把签名信息放进 WebSocket 连接 URL 的查询参数里。
一次鉴权，会话期间持续有效；响应中不含签名。

**WebSocket 地址**：`wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`

## 六步拆解

**Step 1：生成签名原始字符串**
从 wss 地址拆出 `host` 和 path，生成 UTC 的 GMT 时间，拼成三行（注意是 `\n` 换行）：
```
host: avatar.cn-huadong-1.xf-yun.com
date: Mon, 10 Jun 2026 08:00:00 GMT
GET /v1/interact HTTP/1.1
```
- `host`：从 URL 提取的主机名（含非默认端口时追加 `:port`）
- `date`：UTC 时区、RFC 1123 格式（`%a, %d %b %Y %H:%M:%S GMT`）

**Step 2：HMAC-SHA256 签名**
用 `apiSecret` 对 Step 1 的原文做 HMAC-SHA256（编码统一 UTF-8），得到签名字节数组。

**Step 3：Base64 编码签名**
对字节数组做 Base64，得到 `signature` 字符串。

**Step 4：构造 authorization 原文**
```
api_key="<apiKey>", algorithm="hmac-sha256", headers="host date request-line", signature="<signature>"
```
- `api_key`：应用的 apiKey；`algorithm` 固定 `hmac-sha256`；`headers` 固定 `host date request-line`

**Step 5：Base64 编码 authorization 原文**
对 Step 4 整串再做 Base64，得到最终用于 URL 的 `authorization` 值。

**Step 6：拼接 URL**
把 `authorization`、`date`、`host` 三个参数分别 URL 编码后拼到 wss 地址后：
```
wss://avatar.cn-huadong-1.xf-yun.com/v1/interact?authorization=<...>&date=<...>&host=<...>
```

> 常见坑：date 必须是 UTC/GMT；签名原文用 `\n` 连接；authorization 是**两次** Base64（先 Step3 签名、再 Step5 整串）。

## Python 示例

```python
import base64, hashlib, hmac
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

def build_auth_url(ws_url, api_key, api_secret):
    """使用 HMAC-SHA256 生成带鉴权参数的 WebSocket 地址。"""
    parsed = urlparse(ws_url)
    host = parsed.hostname
    if parsed.port and parsed.port not in (80, 443):
        host = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    # Step 1: UTC GMT 时间 + 签名原文
    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    # Step 2+3: HMAC-SHA256 后 Base64
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), origin.encode(), hashlib.sha256).digest()
    ).decode()
    # Step 4: authorization 原文
    authorization = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    # Step 5+6: 再 Base64，URL 编码拼接
    auth_base64 = base64.b64encode(authorization.encode()).decode()
    params = {"authorization": auth_base64, "date": date, "host": host}
    return f"{ws_url}?{urlencode(params)}"
```

## JavaScript 示例（Web Crypto API）

```javascript
async function buildAuthUrl(wsUrl, host, path, apiKey, apiSecret) {
  const date = new Date().toUTCString();
  const signatureOrigin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
  const signature = await hmacSha256(apiSecret, signatureOrigin);
  const authorization = `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${signature}"`;
  const params = new URLSearchParams({
    authorization: btoa(authorization), date, host,
  });
  return `${wsUrl}?${params.toString()}`;
}

async function hmacSha256(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  return btoa(String.fromCharCode(...new Uint8Array(sig)));
}
```

## Java 示例

```java
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;

public class AuthUtil {
    public static String buildAuthUrl(String wsUrl, String apiKey, String apiSecret) {
        try {
            URL url = new URL(wsUrl.replace("ws://", "http://").replace("wss://", "https://"));
            String host = url.getHost();
            if (url.getPort() > 0) host = host + ":" + url.getPort();
            SimpleDateFormat fmt = new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z", Locale.US);
            fmt.setTimeZone(TimeZone.getTimeZone("UTC"));
            String date = fmt.format(new Date());
            String origin = "host: " + host + "\ndate: " + date + "\nGET " + url.getPath() + " HTTP/1.1";
            Mac mac = Mac.getInstance("hmacsha256");
            mac.init(new SecretKeySpec(apiSecret.getBytes(StandardCharsets.UTF_8), "hmacsha256"));
            String signature = Base64.getEncoder().encodeToString(
                    mac.doFinal(origin.getBytes(StandardCharsets.UTF_8)));
            String authorization = String.format(
                    "api_key=\"%s\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"%s\"",
                    apiKey, signature);
            String authBase64 = Base64.getEncoder().encodeToString(authorization.getBytes(StandardCharsets.UTF_8));
            return String.format("%s?authorization=%s&host=%s&date=%s", wsUrl,
                    URLEncoder.encode(authBase64, "UTF-8"),
                    URLEncoder.encode(host, "UTF-8"),
                    URLEncoder.encode(date, "UTF-8"));
        } catch (Exception e) {
            throw new RuntimeException("生成鉴权URL失败: " + e.getMessage(), e);
        }
    }
}
```

> 请求报文构造见 `protocols.md`，响应解读见 `responses.md`。

