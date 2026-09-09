# 控制台获取流程

**📖 完整文档**: https://www.yuque.com/xnrpt/bbc1du/usyebvyczgcy23pk

## 获取流程（根据官方文档）

### 前置说明

接入各 SDK、API 前需提前申请：
- ✅ AppId（应用ID）
- ✅ ApiKey（接口密钥）
- ✅ ApiSecret（接口密钥 Secret）
- ✅ 形象（avatar_id）
- ✅ 发音人（vcn）
- ✅ 并发路数（默认1路）
- ✅ 有效期（默认600分钟免费测试时长）

---

### Step 1: 登录控制台并申请服务

```
控制台地址: https://virtual-man.xfyun.cn/console/projects
```

**操作步骤**:
1. 登录虚拟人交互平台
2. 在首页点击 "开通服务"
3. 填写申请信息
4. 提交申请（等待审核）

⚠️ **注意**: 审核通过后才能继续后续步骤

---

### Step 2: 进入"我的订阅"

**审核通过后**:
1. 进入 "我的订阅" 页面
2. 可以看到申请的 "接口服务" 能力的 appid

⚠️ **交互路数限制**: 
- 默认1路，只能开启1路虚拟人
- 超过该路数会报错 11203

---

### Step 3: 创建接口服务项目

1. 进入 "接口服务" 页面
2. 点击 "创建接口服务" 按钮
3. 填写项目名称
4. 选择服务类型（文本驱动/文本交互/语音交互）
5. 点击 "确定" 创建

---

### Step 4: 获取凭据（appId/apiKey/apiSecret/sceneId）

**进入创建的接口服务项目**:
1. 接口服务 → 我的接口项目 → 编辑
2. 在项目详情中可以看到：
   - **APP_ID**: 应用ID
   - **API_KEY**: 接口密钥
   - **API_SECRET**: 接口密钥 Secret
   - **接口服务ID（SCENE_ID）**: 场景ID/sceneId

⚠️ **重要**: API_SECRET 只显示一次，请立即复制保存！

---

### Step 5: 发布接口服务（必需）

⚠️ **关键步骤**: 必须点击 "发布" 按钮，appid 才能使用！

**发布后**:
- ✅ 接口服务状态变为 "已发布"
- ✅ 获得 600 分钟免费测试时长
- ✅ 时长按 WebSocket 连接时间计算

**未发布的后果**:
- ❌ 连接时会报错 10121（sceneId 未发布）
- ❌ 无法使用任何功能

---

### Step 6: 获取形象和发音人

**进入 "接口服务" → "形象列表"**:

1. **形象列表**（上半部分）:
   - 查看已授权的虚拟人形象
   - 复制 `avatar_id`（形象ID）
   
2. **声音列表**（下半部分，往下滑动）:
   - 查看已授权的发音人
   - 复制 `vcn`（发音人ID）

⚠️ **注意**: 只能使用已授权的形象和发音人

---

## 补充说明

### 检查登录状态

```javascript
function checkConsoleAccess() {
  console.log('🔐 请访问虚拟人交互平台控制台');
  console.log('   https://virtual-man.xfyun.cn/console/projects');
  console.log('');
  console.log('📖 完整接入指南:');
  console.log('   https://www.yuque.com/xnrpt/bbc1du/usyebvyczgcy23pk');
  
  const hasAccount = askUser('是否已有账号？');
  
  if (!hasAccount) {
    console.log('请先注册账号');
    return false;
  }
  
  return true;
}
```

### 创建应用（获取 appId/apiKey/apiSecret）

**操作步骤**:
1. 登录控制台
2. 进入"应用管理"
3. 点击"创建应用"
4. 填写应用名称和描述
5. 创建后获取：
   - `appId`
   - `apiKey`
   - `apiSecret`（⚠️ 只显示一次，请妥善保存）

### 创建接口服务（获取 sceneId）

**操作步骤**:
1. 进入"接口服务"
2. 点击"创建服务"
3. 选择服务类型（文本驱动/文本交互/语音交互）
4. 配置服务参数
5. **发布服务**（⚠️ 必须发布才能使用）
6. 获取 `sceneId`

**检查服务状态**:
```javascript
function checkSceneStatus(sceneId) {
  console.log('⚠️ 重要: sceneId 必须处于"已发布"状态');
  console.log('   未发布的 sceneId 无法使用');
  
  const isPublished = askUser('该接口服务是否已发布？');
  
  if (!isPublished) {
    return {
      valid: false,
      error: 'sceneId 未发布',
      fix: '请在控制台发布该接口服务'
    };
  }
  
  return { valid: true };
}
```

### 授权形象（获取 avatarId）

**操作步骤**:
1. 进入"形象管理"
2. 查看可用形象
3. 授权需要使用的形象
4. 获取 `avatarId`

**形象类型**:
```yaml
标准虚拟人:
  avatarId: 118801001 (示例)
  特点: 支持透明背景、动作控制
  
超拟人:
  avatarId: cnr开头
  特点: 更逼真，但功能受限（不支持透明背景）
```

### 选择发音人（获取 vcn）

**常见发音人**:
```yaml
x4_yezi: 女声，温柔
x4_lingfeng: 男声，成熟
x4_xiaoyuan: 女声，活泼
```

**获取方式**:
- 控制台"发音人管理"
- 或使用默认发音人
