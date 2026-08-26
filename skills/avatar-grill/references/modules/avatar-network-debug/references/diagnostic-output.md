# Step 6: 生成诊断报告 + 快速诊断脚本 + 输出格式

## 6.1 诊断报告结构

```markdown
# 虚拟人网络诊断报告

## 诊断时间
2026-07-13 14:30:00

## 基础网络状态

### 网络连接
- 状态: ✓ 在线
- 类型: WiFi
- 延迟: 25ms (优秀)
- 丢包率: 0%

### DNS 解析
- 域名: avatar.cn-huadong-1.xf-yun.com
- IP 地址: 123.45.67.89
- 解析时间: 15ms
- 状态: ✓ 正常

## WebSocket 连通性

### TCP 连接
- 目标: avatar.cn-huadong-1.xf-yun.com:443
- 状态: ✓ 连接成功
- 耗时: 120ms

### WebSocket 握手
- 状态: ✗ 握手失败
- 错误码: 1008 (Policy Violation)
- 关闭原因: "Invalid authorization"

## 鉴权验证

### 签名生成
- apiKey: ✓ 已配置
- apiSecret: ✓ 已配置
- date 格式: ✗ 错误
  - 当前: "2026-07-13 10:30:00"
  - 正确: "Mon, 13 Jul 2026 10:30:00 GMT"

### 根因分析
**date 格式错误导致签名不匹配**

## 修复建议

### Step 1: 修正 date 格式
```javascript
// ❌ 错误
const date = new Date().toString();

// ✓ 正确
const date = new Date().toUTCString();
```

### Step 2: 重新生成签名
使用正确的 date 格式重新生成 authorization

### Step 3: 验证修复
重新连接，确认收到 avatar_ready 事件

## 参考文档
- 鉴权文档: https://doc.xfyun.cn/avatar/auth
- 错误码说明: https://doc.xfyun.cn/avatar/error-codes
```

## 快速诊断命令

### 一键诊断脚本（Bash）

```bash
#!/bin/bash

echo "=== 虚拟人网络诊断 ==="
echo ""

# 1. 网络状态
echo "1. 网络状态"
ping -c 3 8.8.8.8 > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "✓ 网络连接正常"
else
  echo "✗ 网络连接失败"
  exit 1
fi
echo ""

# 2. DNS 解析
echo "2. DNS 解析"
HOST="avatar.cn-huadong-1.xf-yun.com"
IP=$(nslookup $HOST | grep -A 1 "Name:" | tail -1 | awk '{print $2}')
if [ -n "$IP" ]; then
  echo "✓ DNS 解析成功: $HOST -> $IP"
else
  echo "✗ DNS 解析失败"
  exit 1
fi
echo ""

# 3. TCP 连接
echo "3. TCP 连接测试"
nc -zv $HOST 443 2>&1 | grep succeeded > /dev/null
if [ $? -eq 0 ]; then
  echo "✓ TCP 443 端口连接成功"
else
  echo "✗ TCP 443 端口连接失败"
  exit 1
fi
echo ""

# 4. 网络质量
echo "4. 网络质量测试"
PING_RESULT=$(ping -c 10 $HOST | tail -1)
echo "✓ $PING_RESULT"
echo ""

echo "=== 诊断完成 ==="
```

## 输出格式

### 成功输出
```yaml
status: "network_ok"
checks:
  connectivity: "ok"
  dns: "ok"
  tcp: "ok"
  websocket: "ok"
  stream: "ok"
latency: 25
packet_loss: 0
```

### 问题输出
```yaml
status: "network_issues"
issues:
  - type: "authentication"
    severity: "critical"
    description: "date 格式错误导致签名不匹配"
    fix:
      - "使用 toUTCString() 生成 date"
      - "重新生成 authorization"
```
