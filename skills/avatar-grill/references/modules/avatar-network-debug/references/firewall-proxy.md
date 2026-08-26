# Step 5: 防火墙和代理检查

## 5.1 防火墙规则检查

**需要放行的协议和端口**:
```yaml
WebSocket:
  协议: "WSS (WebSocket Secure)"
  端口: "443"
  域名: "avatar.cn-huadong-1.xf-yun.com"

XRTC/WebRTC:
  协议: "UDP"
  端口范围: "动态端口（通常 10000-65535）"
  用途: "视频流传输"
```

**检查方法**:
```bash
# Windows
netsh advfirewall firewall show rule name=all | findstr 443

# Linux (iptables)
sudo iptables -L -n | grep 443

# macOS
sudo pfctl -s rules | grep 443
```

**配置建议**:
```bash
# Linux (iptables) 放行 443 端口
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

# 放行 UDP（流媒体）
sudo iptables -A OUTPUT -p udp -j ACCEPT
```

## 5.2 代理服务器检查

**检测代理配置**:
```javascript
// Web
console.log('HTTP 代理:', process.env.HTTP_PROXY);
console.log('HTTPS 代理:', process.env.HTTPS_PROXY);

// 检查浏览器代理设置
// Chrome: chrome://settings/?search=proxy
// Firefox: about:preferences#general → Network Settings
```

**代理问题**:
```yaml
问题 1: "代理不支持 WebSocket"
  症状: "HTTP 连接正常，WebSocket 失败"
  fix: "配置代理支持 WebSocket 或绕过代理"

问题 2: "企业代理 SSL 拦截"
  症状: "证书验证失败"
  fix: "导入企业根证书或使用直连"

问题 3: "代理超时设置过短"
  症状: "连接频繁断开"
  fix: "增加代理超时时间"
```

## 5.3 企业网络限制

**常见企业网络限制**:
```yaml
限制 1: "白名单机制"
  描述: "仅允许访问白名单域名"
  fix: "申请将 *.xf-yun.com 加入白名单"

限制 2: "协议限制"
  描述: "禁止 WebSocket 或 UDP"
  fix: "联系网络管理员开放协议"

限制 3: "端口限制"
  描述: "仅开放 80/443 端口"
  fix: "虚拟人服务使用 443，应该可以通过"

限制 4: "带宽限制"
  描述: "限制上传/下载带宽"
  fix: "降低视频码率或使用专线"
```
