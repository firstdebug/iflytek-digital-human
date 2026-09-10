# 问题 6: avatar authentication failed (鉴权失败)

**错误信息**:
```
SDK 加载失败: avatar authentication failed
```

**根本原因**:
这是**服务端返回的鉴权失败**，WebSocket 连接已建立，但签名验证不通过。

**可能原因(按优先级)**:

### 1. sceneId 未发布或已过期 ⭐⭐⭐ (最常见)

**症状**: 凭据都对，但连接失败

**检查**:
1. 登录控制台: https://virtual-man.xfyun.cn/console/projects
2. 进入 "接口服务" → "我的接口项目"
3. 找到你的 sceneId 对应的项目
4. 检查:
   - ✅ 是否点击了 "发布" 按钮？
   - ✅ 状态是否显示 "已发布"？
   - ✅ 是否在有效期内？(免费 600 分钟可能用完)

**修复**: 如果未发布，点击 "发布" 按钮。如果已过期，需要续费或重新申请。

---

### 2. 服务端签名 URL / apiSecret 错误

**症状**: WebSocket 已建立但立即返回 `avatar authentication failed`，或服务端生成的 signed URL 被浏览器复用/篡改。

**检查**:
```bash
python tools/xfyun_query_services.py list-apps
python tools/xfyun_query_services.py list-scenes
python tools/xfyun_model_manage.py check <sceneId>
```

**修复**: 
- Web 端不得暴露 apiSecret；只允许后端用 apiSecret 生成一次性的 signed URL。
- signed URL 只允许带 `authorization/date/host` 这类签名参数，不得把原始密钥下发到前端。
- 如果 apiSecret 丢失或被重置，需要重新生成并更新服务端环境变量，然后重新生成 signed URL。

---

### 3. appId / apiKey / sceneId 不匹配

**症状**: appId、apiKey、sceneId 分别来自不同项目，或 sceneId 不是接口服务项目。

**检查**:
```bash
python tools/xfyun_query_services.py list-apps
python tools/xfyun_query_services.py list-scenes
```

**修复**: 使用同一个接口服务项目下的 appId、apiKey、sceneId；如项目不存在或类型不对，重新创建接口服务：

```bash
python tools/xfyun_interface.py create <appId> <name>
python tools/xfyun_interface.py auth-avatar <appId>
```

---

### 4. 签名算法错误 (代码问题)

**症状**: SDK 版本不匹配或签名参数错误

**检查**:
```javascript
// avatar-service.js 中的 setApiInfo 调用
this.avatar.setApiInfo({
    serverUrl: config.serverUrl,  // 确保是正确的 WSS 地址
    appId: config.appId,
    apiKey: config.apiKey,
    apiSecret: config.apiSecret,
    sceneId: config.sceneId
});
```

**常见错误**:
- serverUrl 写错(http 而非 wss)
- 参数顺序错误
- 参数名拼写错误(appID vs appId)

---

### 5. sceneId 与 appId 不匹配

**症状**: sceneId 来自另一个应用

**检查**: 在控制台确认 sceneId 和 appId 来自**同一个接口服务项目**

---

## 诊断步骤

```bash
# 1. 查询账号下应用，确认 appId/appType
python tools/xfyun_query_services.py list-apps

# 2. 查询接口场景，确认 sceneId 属于当前 appId 且已发布
python tools/xfyun_query_services.py list-scenes

# 3. 检查模型/NLP 绑定是否正常
python tools/xfyun_model_manage.py check <sceneId>

# 4. 必要时重新创建接口项目并授权形象/发音人
python tools/xfyun_interface.py create <appId> <name>
python tools/xfyun_interface.py auth-avatar <appId>

# 5. 浏览器自动采集运行证据，只有 ready_to_deliver=true 才能完成交付
python tools/web_delivery.py
```

---

## 快速自检清单

- [ ] sceneId 已点击"发布"？
- [ ] 接口服务状态显示"已发布"？
- [ ] 免费时长是否还有剩余？(600分钟)
- [ ] appId / apiKey / sceneId 来自同一个接口服务项目？
- [ ] apiSecret 只存在于服务端签名逻辑中，没有下发到浏览器？
- [ ] sceneId 和 appId 来自同一个项目？
- [ ] `web_delivery.py` 已采集到 `connected`、`stream_start`、`first_frame` 等证据？
- [ ] 交付证据中出现 `ready_to_deliver=true`？

---

## 修复流程

### 如果是 sceneId 未发布:
```
1. 登录控制台
2. 接口服务 → 我的接口项目
3. 找到对应项目，点击 "发布"
4. 刷新浏览器页面，重新连接
```

### 如果是凭据错误:
```
1. 用 xfyun_query_services.py list-apps / list-scenes 对齐 appId、apiKey、sceneId
2. 服务端更新 apiSecret，并重新生成 signed URL
3. 重启后端签名服务和前端开发服务器
4. 重新运行 web_delivery.py，直到 ready_to_deliver=true
```

### 如果是时长耗尽:
```
1. 控制台查看剩余时长
2. 如需继续测试，联系平台续费
3. 或创建新的接口服务项目(重新获得 600 分钟)
```

---

## 在线验证

不要手写未证实的控制台 API，也不要在浏览器里打印密钥。按工具链验证：

```bash
python tools/xfyun_query_services.py list-apps
python tools/xfyun_query_services.py list-scenes
python tools/xfyun_model_manage.py check <sceneId>
python tools/web_delivery.py
```

如果缺接口项目或授权资产，先补齐：

```bash
python tools/xfyun_interface.py create <appId> <name>
python tools/xfyun_interface.py auth-avatar <appId>
```

---

## 相关错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|---------|
| 10121 | sceneId 未发布 | 控制台点击"发布" |
| 10112 | appId 不存在 | 检查 appId 是否正确 |
| 10113 | apiKey/apiSecret 错误 | 重新从控制台复制 |
| 10114 | 签名错误 | 检查签名算法实现 |
| 11203 | 并发路数超限 | 关闭其他会话或增加路数 |
| 11206 | 时长耗尽 | 续费或重新申请 |
