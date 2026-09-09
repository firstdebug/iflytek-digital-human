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

### 2. apiSecret 错误

**症状**: apiSecret 复制错了或被修改

**检查**:
```bash
# 查看 .env 中的 apiSecret
cat .env | grep API_SECRET

# 对比控制台里的值(注意只显示一次)
```

**修复**: 
- apiSecret 只在创建时显示一次
- 如果丢失，需要在控制台重新生成(会使旧值失效)

---

### 3. appId 或 apiKey 错误

**症状**: appId/apiKey 复制错误或用错了项目的

**检查**:
```javascript
// 浏览器控制台打印实际使用的凭据
console.log('appId:', import.meta.env.VITE_AVATAR_APP_ID);
console.log('apiKey:', import.meta.env.VITE_AVATAR_API_KEY);

// 对比控制台 "我的接口项目" → "编辑" 里显示的值
```

**修复**: 从控制台重新复制正确的值到 `.env`

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

```javascript
// 1. 打印所有凭据(脱敏 apiSecret)
const config = {
    appId: import.meta.env.VITE_AVATAR_APP_ID,
    apiKey: import.meta.env.VITE_AVATAR_API_KEY,
    apiSecret: import.meta.env.VITE_AVATAR_API_SECRET?.slice(0, 8) + '****',
    sceneId: import.meta.env.VITE_AVATAR_SCENE_ID,
};
console.log('🔑 当前凭据:', config);

// 2. 在控制台对比
// 访问: https://virtual-man.xfyun.cn/console/projects
// 接口服务 → 我的接口项目 → 编辑 → 查看凭据

// 3. 检查 sceneId 发布状态
// 必须显示 "已发布"，否则无法使用
```

---

## 快速自检清单

- [ ] sceneId 已点击"发布"？
- [ ] 接口服务状态显示"已发布"？
- [ ] 免费时长是否还有剩余？(600分钟)
- [ ] appId 是 8 位数字？
- [ ] apiKey 是 32 位十六进制？
- [ ] apiSecret 是 32 位十六进制？
- [ ] sceneId 和 appId 来自同一个项目？
- [ ] .env 文件中凭据前缀是 `VITE_AVATAR_` ？

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
1. 对比控制台和 .env 中的值
2. 重新复制正确的凭据到 .env
3. 重启开发服务器(npm run dev)
4. 刷新浏览器页面
```

### 如果是时长耗尽:
```
1. 控制台查看剩余时长
2. 如需继续测试，联系平台续费
3. 或创建新的接口服务项目(重新获得 600 分钟)
```

---

## 在线验证(avatar-credentials skill)

可以用 `avatar-credentials` skill 的在线验证功能测试凭据:

```javascript
async function verifyCredentials(config) {
    try {
        const response = await fetch(
            `https://virtual-man.xfyun.cn/api/v1/scene/${config.sceneId}/status`,
            {
                headers: {
                    'X-App-Id': config.appId,
                    'X-Api-Key': config.apiKey,
                }
            }
        );
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ 凭据验证通过');
            console.log('场景状态:', data);
            return true;
        } else {
            console.error('❌ 凭据验证失败:', response.status);
            return false;
        }
    } catch (error) {
        console.error('❌ 验证请求失败:', error);
        return false;
    }
}
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
