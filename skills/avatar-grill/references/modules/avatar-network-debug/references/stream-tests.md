# Step 4: 流媒体服务测试

## 4.1 XRTC/WebRTC 连通性

**测试流程**:
```javascript
// 1. 从 start 响应中获取 stream_url
avatar.on(SDKEvents.stream_start, (data) => {
  console.log('流地址:', data.stream_url);
  console.log('协议:', data.protocol);  // xrtc/webrtc
  
  // 2. 测试流连接
  testStreamConnection(data.stream_url);
});

function testStreamConnection(streamUrl) {
  const startTime = Date.now();
  
  // 等待首帧
  player.on('first_frame', () => {
    const elapsed = Date.now() - startTime;
    console.log(`✓ 首帧渲染耗时: ${elapsed}ms`);
  });
  
  // 超时检测
  setTimeout(() => {
    if (!receivedFirstFrame) {
      console.error('✗ 首帧超时（15s）');
      diagnoseStreamIssue();
    }
  }, 15000);
}
```

**流媒体问题诊断**:
```yaml
首帧超时:
  原因:
    - "网络带宽不足"
    - "流媒体服务不可达"
    - "NAT 穿透失败"
  fix:
    - "降低视频码率和帧率"
    - "检查防火墙 UDP 端口"
    - "更换网络环境"

播放卡顿:
  原因:
    - "网络质量差，丢包严重"
    - "设备解码能力不足"
  fix:
    - "降低分辨率和码率"
    - "检查设备性能"
```
