# Step 2: WebSocket 连通性测试

## 2.1 TCP 连接测试

**测试端口连通性**:
```bash
# 使用 telnet
telnet avatar.cn-huadong-1.xf-yun.com 443

# 使用 nc (netcat)
nc -zv avatar.cn-huadong-1.xf-yun.com 443

# 使用 curl（WebSocket）
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" \
     -H "Sec-WebSocket-Key: test" \
     https://avatar.cn-huadong-1.xf-yun.com/v1/interact
```

**失败原因诊断**:
```yaml
Connection refused:
  原因: "端口未开放或服务未运行"
  fix: "确认服务地址正确"

Connection timeout:
  原因: "防火墙阻止或网络不可达"
  fix: "检查防火墙规则"

Network unreachable:
  原因: "本地网络配置问题"
  fix: "检查路由和网关"
```

## 2.2 WebSocket 握手测试

**使用代码测试握手**:
```javascript
// Web
const testWebSocket = () => {
  const ws = new WebSocket('wss://avatar.cn-huadong-1.xf-yun.com/v1/interact?...');
  
  ws.onopen = () => {
    console.log('✓ WebSocket 连接成功');
    ws.close();
  };
  
  ws.onerror = (err) => {
    console.error('✗ WebSocket 连接失败:', err);
  };
  
  ws.onclose = (event) => {
    console.log('连接关闭:', event.code, event.reason);
  };
  
  // 设置超时
  setTimeout(() => {
    if (ws.readyState !== WebSocket.OPEN) {
      console.error('✗ 连接超时');
      ws.close();
    }
  }, 10000);
};
```

**WebSocket 关闭码诊断**:
```yaml
1000 (Normal Closure):
  含义: "正常关闭"
  action: "无需处理"

1001 (Going Away):
  含义: "服务端关闭连接"
  action: "检查服务状态"

1006 (Abnormal Closure):
  含义: "异常关闭（网络中断或超时）"
  action: "检查网络稳定性"

1008 (Policy Violation):
  含义: "违反策略（通常是鉴权失败）"
  action: "检查凭据和签名"

1011 (Internal Error):
  含义: "服务端内部错误"
  action: "联系技术支持"
```
