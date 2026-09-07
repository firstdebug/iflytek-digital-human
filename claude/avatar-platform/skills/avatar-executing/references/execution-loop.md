# 执行循环 (Step 3)

逐步执行实现计划中的每个步骤，选择合适的 writer/reviewer，应用变更并验证。

## Step 3.0: 前置检查 — SDK 下载（必需）

**在执行任何代码生成前**，必须确保 SDK 文件已下载到项目目录。

```javascript
// 执行循环开始前的强制检查
async function ensureSDKDownloaded(platform, projectPath) {
  console.log(`[前置] 检查 ${platform} SDK...`);
  
  // 调用 avatar-artifact-download skill
  const downloadResult = await invokeSkill('avatar-artifact-download', {
    platform: platform,
    projectPath: projectPath
  });
  
  if (downloadResult.status === 'success') {
    console.log(`✓ SDK 已就绪: ${downloadResult.path}`);
  } else if (downloadResult.status === 'already_exists') {
    console.log(`✓ SDK 已存在，跳过下载`);
  } else {
    console.error(`SDK 未就绪: ${downloadResult.status}`);
    throw new Error('blocked_missing_sdk');
  }
  
  return downloadResult;
}

// 在主循环前调用
await ensureSDKDownloaded(platform, projectPath);
```

**规则**：
- ✅ Android/iOS 项目：必须下载 SDK
- ✅ Web 项目：必须下载 SDK
- ❌ 不允许跳过此步骤
- ❌ 不允许手写 WebSocket 协议代替 SDK

---

## Step 3.1: 主执行循环

```javascript
for (const step of plan.steps) {
  console.log(`执行 ${step.id}: ${step.title}`);
  
  // 3.1.1 选择 code-writer
  const writer = shouldUseAvatarWriter(step) 
    ? 'avatar-code-writer' 
    : 'code-writer';
  
  // 3.1.2 生成代码（传递【权威 API 文档】路径 —— 见下方 HARD-GATE）
  const codeChanges = await runSubAgent(writer, {
    step: step,
    platform: platform,
    context: projectContext,
    apiDoc: getAuthoritativeApiDocPath(platform)  // ⚠️ Android/Web 必须传 playbook，禁止传手搓的 api-notes
  });
  
  // 3.1.3 应用代码变更
  await applyChanges(codeChanges);
  
  // 3.1.4 选择 code-reviewer
  const reviewer = shouldUseAvatarReviewer(step)
    ? 'avatar-code-reviewer'
    : 'code-reviewer';
  
  // 3.1.5 代码评审（reviewer 也必须拿到同一份权威 API 文档）
  const reviewResult = await runSubAgent(reviewer, {
    changes: codeChanges,
    step: step,
    apiDoc: getAuthoritativeApiDocPath(platform)
  });
  
  if (reviewResult.status === 'fail') {
    // 修复问题后重新生成
    await fixAndRetry(reviewResult.issues);
  }
  
  // 3.1.6 验证步骤
  const verifyResult = await verifyStep(step);
  
  if (!verifyResult.pass) {
    console.error(`${step.id} 验证失败:`, verifyResult.errors);
    // 决策: 修复 / 跳过 / 中止
    await handleVerificationFailure(step, verifyResult);
  }
  
  console.log(`✓ ${step.id} 完成`);
}
```

---

## 辅助函数

### getAuthoritativeApiDocPath() —— 唯一权威 API 来源（HARD-GATE）

```javascript
function getAuthoritativeApiDocPath(platform) {
  // ⚠️ Android/Web 首次接入：唯一权威 API 来源是 playbook，不是 integration-guides/*.md。
  //   integration-guides/android.md 是【人工简化失真版】，含 createStreamPlayer/sendText/onNlpResult
  //   等不存在的 API，照它写必崩。playbook §1 是 javap 反编译的真实全表 + 已真机验证。
  const authoritative = {
    'web':     'skills/avatar-executing/references/web-sdk-build-playbook.md',
    'android': 'skills/avatar-executing/references/android-sdk-build-playbook.md',
    // Android 另附逐字可复用模板：
    // skills/avatar-executing/references/android-mainactivity-template.java
    'ios':     'skills/integration-guides/ios.md'  // iOS 暂无 playbook，用集成指南
  };

  const docPath = authoritative[platform.toLowerCase()];
  if (!docPath) {
    throw new Error(`未找到 ${platform} 的权威 API 文档`);
  }
  return docPath;
}

// ❌ 已废弃：getIntegrationGuidePath()。它指向 integration-guides/android.md（失真文档），
//    是历史踩坑根因。任何派发 writer/reviewer 的地方都必须改用 getAuthoritativeApiDocPath()。
```

### shouldUseAvatarWriter()

使用领域适配 writer 的条件：
- SDK 初始化
- 播放器创建
- 参数配置
- 事件监听
- 文本/语音交互
- WebSocket 鉴权

### shouldUseAvatarReviewer()

使用领域适配 reviewer 的条件：
- 与 shouldUseAvatarWriter 相同的步骤
- 需要检查 SDK API 使用是否正确
- 需要检查是否避免了手写 WebSocket

---

## 关键检查点

### 检查点 1: SDK 文件存在性

```javascript
function verifySDKFiles(platform, projectPath) {
  const requiredFiles = {
    'android': [
      'app/libs/avatar-core-*.aar',
      'app/libs/xrtcsdk-*.aar'
    ],
    'ios': [
      'Frameworks/AvatarSDK.framework',
      'Frameworks/XRTCSDK.framework'
    ],
    'web': [
      'sdk/**/index.js'
    ]
  };
  
  const files = requiredFiles[platform];
  for (const pattern of files) {
    if (!fileExists(projectPath, pattern)) {
      throw new Error(`缺少 SDK 文件: ${pattern}`);
    }
  }
  
  return true;
}
```

### 检查点 2: 集成指南引用

```javascript
function verifyRealSdkApiUsed(codeChanges, platform) {
  const code = codeChanges.map(c => c.content).join('\n');

  // (a) 必须出现的【真实】SDK API（避免手写 WebSocket）
  const requiredAPIs = {
    // ⚠️ Android 真实 API：createPlayer（不是 createStreamPlayer）、writeText（不是 sendText）
    'android': ['AvatarPlatform.initialize', 'StreamPlayerFactory.createPlayer', 'setRenderArea'],
    'ios': ['AvatarPlatform', 'createPlayer'],
    'web': ['AvatarPlatform', 'setApiInfo']
  };
  const apis = requiredAPIs[platform];
  if (!apis.some(api => code.includes(api))) {
    throw new Error(`代码未使用真实 SDK API，疑似手写 WebSocket。权威文档: ${getAuthoritativeApiDocPath(platform)}`);
  }

  // (b) 【失真 API 黑名单】—— 出现任一即判定照了失真文档，必须打回重写
  const FORBIDDEN_APIS = [
    'createStreamPlayer', 'sendText', 'onNlpResult', 'onAsrResult',
    'onAvatarReady', 'writeAudioFrame', 'startAudioInteract', 'setApiKey('
  ];
  const hit = FORBIDDEN_APIS.filter(api => code.includes(api));
  if (hit.length > 0) {
    throw new Error(`[HARD-GATE] 检测到失真文档 API（真实 SDK 中不存在）: ${hit.join(', ')}。` +
      `必须按 ${getAuthoritativeApiDocPath(platform)} §1 真实签名重写。`);
  }

  return true;
}
```

### 检查点 3: 固定模板使用

```javascript
function verifyAssetsFromProbe(codeChanges, probedAvatarId, probedVcn) {
  // ⚠️ 不要硬编码 avatarId/vcn。它们必须来自 auth-avatar 探测结果（因账号而异）。
  //   本函数校验代码里用的就是【本次探测到的】值，而不是任何写死的历史值。
  const code = codeChanges.map(c => c.content).join('\n');

  if (!probedAvatarId || !probedVcn) {
    throw new Error('缺少探测到的 avatarId/vcn。先跑 xfyun_interface.py auth-avatar <appId> 获取，再写代码。');
  }
  if (!code.includes(probedAvatarId)) {
    console.warn(`⚠️ 代码未包含探测到的 avatarId=${probedAvatarId}`);
  }
  if (!code.includes(probedVcn)) {
    console.warn(`⚠️ 代码未包含探测到的 vcn=${probedVcn}`);
  }
  return true;
}
```

---

## 错误处理

### SDK 下载失败

```javascript
if (sdkDownloadFailed) {
  console.error('blocked_missing_sdk');
  console.log('检查网络、下载源、目标目录权限和 sdk-artifact.json 后重试');
  throw new Error('blocked_missing_sdk');
}
```

### 手写 WebSocket 检测

```javascript
if (detectHandWrittenWebSocket(code)) {
  console.error('❌ 检测到手写 WebSocket 协议代码');
  console.error('必须使用 SDK 提供的 API，不允许手写 WebSocket');
  console.log(`请参考权威 API 文档: ${getAuthoritativeApiDocPath(platform)}`);
  throw new Error('禁止手写 WebSocket 协议');
}
```

---

## 总结

执行循环的关键改进：
1. ✅ **Step 3.0 强制下载 SDK** — 在任何代码生成前
2. ✅ **传递权威 API 文档** — `getAuthoritativeApiDocPath()` 给 writer 和 reviewer 传 **playbook**
   （Android/Web），**绝不**传 integration-guides/*.md 失真文档，也不用主 agent 手搓的 api-notes
3. ✅ **失真 API 黑名单校验** — `verifyRealSdkApiUsed()` 检测 createStreamPlayer/sendText/
   onNlpResult 等不存在的 API，命中即打回重写（HARD-GATE）
4. ✅ **资产来自探测** — `verifyAssetsFromProbe()` 校验 avatarId/vcn 用的是 auth-avatar 探测值，
   不硬编码历史值
5. ✅ **明确错误处理** — SDK 下载失败中止执行

> **派发 writer/reviewer 子 agent 的铁律**：无论主 agent 自己是否读过 playbook，派发给
> 写代码/评审的子 agent 时，**必须在 prompt 里带上 playbook 全路径并要求它先读**。子 agent
> 不共享主 agent 的上下文——主 agent 读了不等于子 agent 读了。这是历史上"门禁读了却照样踩坑"
> 的根因：真正写代码的子 agent 从没拿到 playbook。

