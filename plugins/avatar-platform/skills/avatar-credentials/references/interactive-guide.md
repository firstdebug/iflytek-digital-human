# 交互式引导（核心实现）

## Step-by-Step 交互流程

## Phase 1: 检查现有状态

1. 检查是否已有 .env 文件
2. 如果有，读取并验证格式
3. 如果格式正确，询问是否重新配置

## Phase 2: 打开控制台和文档（自动化）

使用 Bash 或 PowerShell 打开浏览器：

```bash
# Windows - 打开控制台和官方文档
powershell -Command "Start-Process 'https://virtual-man.xfyun.cn/console/projects'"
powershell -Command "Start-Process 'https://www.yuque.com/xnrpt/bbc1du/usyebvyczgcy23pk'"

# macOS/Linux
open 'https://virtual-man.xfyun.cn/console/projects' || xdg-open 'https://virtual-man.xfyun.cn/console/projects'
open 'https://www.yuque.com/xnrpt/bbc1du/usyebvyczgcy23pk' || xdg-open 'https://www.yuque.com/xnrpt/bbc1du/usyebvyczgcy23pk'
```

## Phase 3: Step 1 - 获取 appId/apiKey/apiSecret/sceneId

**显示指引**:
```
╔════════════════════════════════════════════╗
║  Step 1/3: 获取接口服务凭据                ║
╚════════════════════════════════════════════╝

📖 官方文档已在浏览器打开，请参考操作

📝 操作步骤（按官方文档）:

1️⃣  申请服务（首次使用）
   → 在控制台首页点击 "开通服务"
   → 填写申请信息并提交
   → 等待审核通过

2️⃣  进入 "我的订阅"
   → 查看已审核通过的 appid

3️⃣  创建接口服务项目
   → 进入 "接口服务" 页面
   → 点击 "创建接口服务"
   → 填写项目名称
   → 选择服务类型（文本驱动/文本交互）
   → 点击 "确定"

4️⃣  获取凭据
   → 接口服务 → 我的接口项目 → 编辑
   → 在项目详情中可以看到:
      • APP_ID (appId)
      • API_KEY (apiKey)
      • API_SECRET (apiSecret)
      • 接口服务ID (sceneId)

5️⃣  ⚠️  重要: 点击 "发布" 按钮
   → 必须发布后 appid 才能使用！
   → 未发布会报错 10121

⚠️  apiSecret 只显示一次，请立即复制保存！

════════════════════════════════════════════
```

**使用 平台交互提问 逐个获取**:
```javascript
// 1. appId
const appId = await askUser({
  question: "请输入你的 appId（8位数字）",
  validation: /^\d{8}$/,
  errorMsg: "appId 应该是 8 位数字"
});

// 2. apiKey  
const apiKey = await askUser({
  question: "请输入你的 apiKey（32位十六进制）",
  validation: /^[a-f0-9]{32}$/,
  errorMsg: "apiKey 应该是 32 位十六进制"
});

// 3. apiSecret
const apiSecret = await askUser({
  question: "请输入你的 apiSecret（32位十六进制）",
  validation: /^[a-f0-9]{32}$/,
  errorMsg: "apiSecret 应该是 32 位十六进制"
});

// 实时验证格式
if (validate) {
  console.log('✅ Step 1 完成');
} else {
  console.log('❌ 格式错误，请重新输入');
  // 重新输入
}
```

## Phase 4: Step 2 - 获取 avatarId 和 vcn

**显示指引**:
```
╔════════════════════════════════════════════╗
║  Step 3/4: 授权形象                        ║
╚════════════════════════════════════════════╝

📝 操作步骤:
1. 在控制台左侧菜单，点击"形象管理"
2. 查看可用形象列表
3. 选择一个形象，点击"授权"按钮
4. 获取 avatarId

💡 形象类型:
   - 标准虚拟人: 纯数字（如 118801001）
     支持透明背景、动作控制
   
   - 超拟人: cnr 开头（如 cnr12345）
     更逼真，但不支持透明背景

════════════════════════════════════════════
```

**获取 avatarId**:
```javascript
const avatarId = await askUser({
  question: "请输入你的 avatarId（纯数字或 cnr 开头）",
  validation: /^\d+$|^cnr/,
  errorMsg: "avatarId 应该是纯数字或 cnr 开头"
});
```

## Phase 6: Step 4 - 选择发音人

**显示选项**:
```
╔════════════════════════════════════════════╗
║  Step 4/4: 选择发音人                      ║
╚════════════════════════════════════════════╝

请选择发音人（vcn）:

1. x4_yezi      - 女声，温柔亲切
2. x4_lingfeng  - 男声，成熟稳重
3. x4_xiaoyuan  - 女声，活泼可爱
4. 其他         - 自定义输入

════════════════════════════════════════════
```

**使用 平台交互提问 选择**:
```javascript
const vcnChoice = await askUserQuestion({
  question: "请选择发音人",
  options: [
    { label: "x4_yezi", description: "女声，温柔亲切" },
    { label: "x4_lingfeng", description: "男声，成熟稳重" },
    { label: "x4_xiaoyuan", description: "女声，活泼可爱" },
    { label: "其他", description: "自定义输入" }
  ]
});

let vcn;
if (vcnChoice === '其他') {
  vcn = await askUser({ question: "请输入发音人 ID:" });
} else {
  vcn = vcnChoice;
}
```

## Phase 7: 保存和验证

**汇总显示**:
```
╔════════════════════════════════════════════╗
║  凭据汇总                                  ║
╚════════════════════════════════════════════╝

appId:       12345678
apiKey:      abcd...
apiSecret:   ****（已隐藏）
sceneId:     scene...
avatarId:    118801001
vcn:         x4_yezi

════════════════════════════════════════════
🔍 正在验证凭据有效性...
```

**在线验证**:
```javascript
try {
  // 尝试建立 WebSocket 连接测试
  await testConnection(credentials);
  console.log('✅ 凭据验证成功');
} catch (error) {
  console.error('❌ 验证失败:', error.message);
  // 根据错误码提示修复
}
```

**保存到 .env**:
```javascript
const envContent = `
# 虚拟人平台凭据
# 生成时间: ${new Date().toISOString()}

APP_ID=${appId}
API_KEY=${apiKey}
API_SECRET=${apiSecret}
SCENE_ID=${sceneId}
AVATAR_ID=${avatarId}
VCN=${vcn}
WS_URL=wss://avatar.cn-huadong-1.xf-yun.com/v1/interact
`;

// 仅写入 Node 服务端读取的 .env；不得使用 VITE_ 前缀暴露 Key/Secret
fs.writeFileSync('.env', envContent);
console.log('✅ 凭据已保存到 .env 文件');
```

**检查 .gitignore**:
```javascript
// 确保 .env 在 .gitignore 中
const gitignore = fs.readFileSync('.gitignore', 'utf-8');
if (!gitignore.includes('.env')) {
  fs.appendFileSync('.gitignore', '\n.env\n');
  console.log('✅ 已将 .env 添加到 .gitignore');
}
```

## Phase 8: 完成提示

```
╔════════════════════════════════════════════╗
║  ✅ 凭据配置完成！                         ║
╚════════════════════════════════════════════╝

📁 凭据已保存到: .env
🔒 安全提示: 不要将 .env 文件提交到 Git

📋 下一步:
  1. SDK 下载和配置
  2. 启动项目

════════════════════════════════════════════
```
