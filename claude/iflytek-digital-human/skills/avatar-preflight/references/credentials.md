# Layer 1: 凭据验证

## Step 1.1: 凭据读取

**读取来源**:

1. 从环境变量读取: `AVATAR_APP_ID`, `AVATAR_API_KEY`, `AVATAR_API_SECRET`, `AVATAR_SCENE_ID`
2. 从配置文件读取:
   - Web: `.env` / `config.js`
   - Android: `AvatarConfig.java` / `build.gradle`
   - iOS: `AvatarConfig.h` / `Info.plist`
3. 从 dev-env.yaml 读取历史记录
4. 缺失时提示用户输入

**用户输入提示**:
```
需要以下凭据（从虚拟人交互平台获取）:

1. appId: 控制台-应用管理-应用列表
2. apiKey / apiSecret: 同上
3. sceneId: 控制台-接口服务-接口服务ID

请输入或配置到环境变量中。
```

**保存策略**:
```yaml
# 保存到 ~/.avatar-code/dev-env.yaml
credentials:
  appId: "xxxxx"
  sceneId: "xxxxx"
  # apiSecret 不保存，每次从环境变量或用户输入读取
```

**PASS 标志**: 四项凭据全部获取
**FAIL 处理**: 提示缺失项，给出获取路径的直达链接

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
