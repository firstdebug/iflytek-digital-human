# Layer 4: 网络连通性检查（所有平台必选）

## Step 4.1: WebSocket 服务连通性

**检查项**:
```
服务地址: wss://avatar.cn-huadong-1.xf-yun.com/v1/interact
```

**检查方式**:
```javascript
// 1. 测试 TCP 连接（Bash）
timeout 5 bash -c "</dev/tcp/avatar.cn-huadong-1.xf-yun.com/443" 2>/dev/null

// 2. 测试 WebSocket 握手（使用凭据）
const ws = new WebSocket(authUrl);
ws.onopen = () => PASS("WebSocket 连接成功");
ws.onerror = (err) => FAIL("连接失败", err);

// 3. 测试鉴权握手
// 发送 start 协议，等待 avatar_ready
```

**PASS 标志**: 连接成功，收到 avatar_ready
**FAIL 处理**:
```
网络不可达 → 检查防火墙、代理、DNS
握手失败 → 重新检查凭据（返回 Layer 1）
超时 → 网络质量差，建议优化或更换网络
```

---

## Step 4.2: 流媒体服务连通性（可选）

**检查项**:
```
测试 XRTC/WebRTC 流推送是否正常
```

**检查方式**:
```
1. 从 start 响应中获取 stream_url
2. 尝试连接流地址
3. 等待首帧渲染（超时 15s）
```

**PASS 标志**: 可以接收流并渲染首帧
**FAIL 处理**: 
```
流地址无法访问 → 网络限制或服务异常
首帧超时 → 网络质量差或播放器配置问题
```

**注意**: 此步骤为可选，失败不阻塞后续流程

---

## Layer 6: 最小验证 - 通用说明

**目的**: 确保从 SDK 初始化到首帧渲染的完整链路通畅

**使用真实配置**:
- 从 dev-env.yaml 读取凭据
- 使用已验证的 avatarId/vcn
- 最简参数（720x1280, fps=25, bitrate=2000）

**必需事件序列**（各平台事件名见对应实现 reference）:
```
1. SDK 初始化成功
2. WebSocket 连接成功（收到 SDKEvents.connected 或类似事件）
3. 收到 stream_start（云端开始推流）
4. 播放器首帧渲染
```

**PASS 标志**: 完整链路通畅，看到虚拟人视频
**FAIL 处理**: 根据失败阶段给出诊断和修复建议

> 平台专属的生成内容、执行命令、事件名详见：
> `web-implementation.md` / `android-implementation.md` / `ios-implementation.md`
