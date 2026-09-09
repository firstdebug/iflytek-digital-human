# Step 1: 基础网络检查

## 1.1 网络连接状态

**检查方法**:
```javascript
// Web
const isOnline = navigator.onLine;
console.log('网络状态:', isOnline ? '在线' : '离线');

// 监听网络变化
window.addEventListener('online', () => console.log('网络恢复'));
window.addEventListener('offline', () => console.log('网络断开'));

// Android
ConnectivityManager cm = (ConnectivityManager) 
    context.getSystemService(Context.CONNECTIVITY_SERVICE);
NetworkInfo activeNetwork = cm.getActiveNetworkInfo();
boolean isConnected = activeNetwork != null && activeNetwork.isConnectedOrConnecting();

// iOS
Reachability *reachability = [Reachability reachabilityForInternetConnection];
NetworkStatus status = [reachability currentReachabilityStatus];
```

## 1.2 DNS 解析测试

**测试服务器域名解析**:
```bash
# 测试虚拟人服务域名
nslookup avatar.cn-huadong-1.xf-yun.com

# 或使用 ping（ICMP 可能被禁用）
ping avatar.cn-huadong-1.xf-yun.com

# 或使用 dig
dig avatar.cn-huadong-1.xf-yun.com
```

**常见 DNS 问题**:
```yaml
解析失败:
  原因: "DNS 服务器无法访问或域名不存在"
  fix: "更换 DNS 服务器（8.8.8.8 或 114.114.114.114）"

解析超时:
  原因: "网络慢或 DNS 服务器响应慢"
  fix: "检查网络质量或更换 DNS"

解析到错误 IP:
  原因: "DNS 劫持或缓存污染"
  fix: "清除 DNS 缓存或使用 HTTPS"
```

## 1.3 网络质量测试

**测试延迟和丢包率**:
```bash
# 持续 ping 测试
ping -c 10 avatar.cn-huadong-1.xf-yun.com

# 分析结果
# rtt min/avg/max/mdev = 20.1/25.3/35.2/4.5 ms
# 0% packet loss
```

**网络质量评估**:
```yaml
优秀:
  延迟: "< 50ms"
  丢包: "0%"
  评级: "适合实时语音交互"

良好:
  延迟: "50-100ms"
  丢包: "< 1%"
  评级: "可正常使用，偶尔延迟"

较差:
  延迟: "100-200ms"
  丢包: "1-5%"
  评级: "体验下降，建议优化网络"

很差:
  延迟: "> 200ms"
  丢包: "> 5%"
  评级: "不建议使用，严重卡顿"
```
