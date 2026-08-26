# Layer 1: 凭据验证

## Step 1.1: 凭据读取

**读取来源**:

1. appId、sceneId 和发布状态从已确认契约及本轮平台查询读取。
2. apiKey/apiSecret 由平台工具取得并通过安全写入脚本落到目标工程；不得进入对话或契约。
3. 现有 `.env` / Android / iOS 配置只用于检查键存在性和当前工程状态，不回显密钥值。
4. 不读取跨任务环境缓存，不要求用户手输可由平台工具取得的事实。

缺失时契约进入 `blocked`。若需要写 `.env`，必须先有 `write_env` 授权；没有授权则回到 Grill 更新并重新确认契约。

**PASS 标志**: 四项凭据全部获取
**FAIL 处理**: 记录缺失项、工具错误和恢复条件，不猜测或回显凭据

---

## Step 1.2: 凭据有效性验证

**目的**: 验证凭据正确性，避免后续开发浪费时间

**验证方法**:
```javascript
// 1. 生成鉴权签名
const authUrl = buildAuthUrl(
  'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
  apiKey,
  apiSecret
);

// 2. 尝试建立测试连接
const ws = new WebSocket(authUrl);

// 3. 发送 start 协议（使用最小参数）
ws.send(JSON.stringify({
  header: { app_id: appId, ctrl: 'start', scene_id: sceneId, request_id: uuid() },
  parameter: { avatar: { avatar_id: 'test', width: 720, height: 1280 } }
}));

// 4. 等待响应
// PASS: 收到 avatar_ready 或 stream_info
// FAIL: 连接拒绝、鉴权失败、sceneId 不存在
```

**PASS 标志**: 收到成功响应（event_type=avatar_ready 或 stream_info）
**FAIL 处理**: 根据错误码明确指出问题
```
10110: appId 不存在或格式错误
10113: apiSecret 错误或签名生成有误
10114: sceneId 不存在或未发布 → 使用 xfyun_interface.py create 创建场景
网络超时: 网络不可达，检查防火墙/代理
```

**注意**: 测试连接后立即断开，避免占用并发路数

---

## 场景不存在时的处理（10114 错误）

当凭据验证返回 `10114: sceneId 不存在或未发布` 时，说明应用存在但场景不存在。

**正确处理流程**:
```python
if error_code == 10114:
    print("[检测] sceneId 不存在")
    print("[解决] 自动创建接口场景...")
    
    # 使用 xfyun_interface.py 创建场景
    result = subprocess.run([
        'python', 'tools/xfyun_interface.py', 
        'create', app_id, scene_name,
        '--desc', description,
        '--welcome', welcome_message
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        # 从输出中提取 sceneId
        scene_id = extract_scene_id(result.stdout)
        print(f"[完成] 场景已创建: {scene_id}")
        # 继续验证流程
    else:
        print("[失败] 场景创建失败")
        print(result.stderr)
```

**说明**:
- 只有**应用不存在**时才需要在控制台创建应用（appType=1 接口服务）
- **场景不存在**时直接使用 `tools/xfyun_interface.py create` 自动创建
- 场景创建会自动配置 NLP、交互参数并发布
- 创建后会自动授权可用的形象和发音人
