# Phase 1: 扫描工程现状

**目的**: 收集工程上下文，为后续决策提供依据

## 1.0 扫描模式选择

**判断逻辑**:
1. 如果用户提供了明确的项目路径（参数 `project_path`）→ 只扫描该目录
2. 如果用户需求明确是"从零开始"/"新建项目"/"没有项目" → 跳过扫描，直接询问目标平台和工作目录
3. 如果当前目录看起来像项目根目录（有 package.json/build.gradle 等）→ 扫描当前目录
4. 否则 → 询问用户是扫描现有项目还是创建新项目

**新项目流程（跳过扫描）**:
```yaml
# 直接询问用户
questions:
  - 目标平台: web | android | ios
  - 工作目录: 用户指定新项目路径（如 D:/my-avatar-project）
  - 项目名称: 可选，默认使用目录名

# 直接输出
platform: web  # 用户选择
confidence: high
evidence: ["用户明确指定"]
sdk_status: not_integrated
project_path: "D:/my-avatar-project"
```

## 1.1 平台识别（仅在扫描模式下执行）

**扫描规则** (参考 `platform-registry.yaml`):
```
Web:
  - package.json + index.html
  - *.html + */avatar-sdk-web*
  - vite.config.* / webpack.config.*

Android:
  - build.gradle + AndroidManifest.xml
  - app/build.gradle

iOS:
  - *.xcodeproj + Info.plist
  - *.xcworkspace + Podfile
```

**输出**:
```yaml
platform: web | android | ios | unknown
confidence: high | medium | low
evidence:
  - "发现 package.json 和 index.html"
  - "发现 Vite 配置文件"
```

**无法识别时**: 使用 AskUserQuestion 询问用户

---

## 1.2 SDK 集成状态检查

**检查项**:
```javascript
已集成:
  - Web: 是否已有 avatar-sdk-web/ 目录
  - Android: 是否有 avatar-core-*.aar
  - iOS: 是否有 AvatarSDK.framework

配置文件:
  - Web: .env / config.js
  - Android: AvatarConfig.java
  - iOS: AvatarConfig.h

已有代码:
  - 搜索 "AvatarPlatform" / "avatar" 关键字
  - 识别已实现的功能
```

**输出**:
```yaml
sdk_status: not_integrated | partially_integrated | fully_integrated
existing_features:
  - text_driver
  - voice_interact
missing_features:
  - action_control
  - transparent_bg
```

---

## 1.3 依赖与工具链扫描

**检查项**:
```
Web:
  - Node.js 版本
  - 构建工具（Vite/Webpack/Rollup）
  - 是否使用 TypeScript

Android:
  - Gradle 版本
  - minSdkVersion
  - 已有依赖（OkHttp/Gson 等）

iOS:
  - Xcode 项目配置
  - CocoaPods / SPM
  - iOS Deployment Target
```

**输出**:
```yaml
environment:
  web:
    node_version: "18.x"
    build_tool: "vite"
    typescript: true
  android:
    gradle_version: "7.2"
    min_sdk: 21
  ios:
    xcode: "14.3"
    deployment_target: "13.0"
```

---

## 1.4 应用类型检测（SDK 集成必需）

**检查时机**: Phase 1 扫描阶段，在平台和 SDK 状态确认后

**目的**: 确保选择的应用类型与交付形态匹配

### 应用类型区分（CRITICAL）

| 应用类型 | appType | 用途 | 适用场景 |
|---------|---------|------|---------|
| 接口服务 | 1 | SDK 集成开发 | 需要自己写代码、深度定制 UI |
| Web 对话 | 2 | 零代码快速部署 | 智能客服、H5 页面、快速演示 |

**关键规则**: 
- SDK 集成项目（用户选择"接 SDK 自建"）**必须**使用 `appType=1` 的应用
- Web 模板项目（用户选择"官方模板"）**必须**使用 `appType=2` 的应用

### 检查流程

```python
def validate_app_type_for_delivery(delivery_mode, selected_app):
    """
    验证应用类型是否匹配交付形态
    
    Args:
        delivery_mode: 'sdk_integration' | 'web_template' | 'live_streaming'
        selected_app: 用户选择的应用
    
    Returns:
        dict: {valid: bool, reason: str, action: str}
    """
    app_type = selected_app.get('appType')
    app_id = selected_app.get('appId')
    app_name = selected_app.get('appName')
    
    # SDK 集成必须是 appType=1
    if delivery_mode == 'sdk_integration':
        if app_type != 1:
            return {
                'valid': False,
                'reason': f'应用 {app_name} (appId={app_id}) 的类型为 appType={app_type}',
                'detail': 'SDK 集成项目必须使用 appType=1（接口服务）的应用',
                'action': 'create_new_app_type1_or_select_another'
            }
    
    # Web 模板必须是 appType=2
    elif delivery_mode == 'web_template':
        if app_type != 2:
            return {
                'valid': False,
                'reason': f'应用 {app_name} (appId={app_id}) 的类型为 appType={app_type}',
                'detail': 'Web 模板项目必须使用 appType=2（Web对话）的应用',
                'action': 'create_new_app_type2_or_select_another'
            }
    
    # 检查对话能力
    has_llm = check_llm_capability(selected_app)
    if not has_llm and delivery_mode in ['sdk_integration', 'web_template']:
        return {
            'valid': False,
            'reason': f'应用 {app_name} 没有大模型对话能力',
            'detail': '需要 LLM_DIALOG_NUM / LLM_DOC_NUM / LLM_TOKENS_NUM 授权',
            'action': 'enable_llm_capability'
        }
    
    return {'valid': True, 'appId': app_id, 'appName': app_name}
```

### 查询并过滤应用

```python
# 查询所有应用
all_apps = query_apps(session)

# 根据交付形态过滤
if delivery_mode == 'sdk_integration':
    valid_apps = [app for app in all_apps 
                  if app.get('appType') == 1 
                  and check_llm_capability(app)]
    
    if not valid_apps:
        print("[阻塞] 没有可用于 SDK 集成的应用（需要 appType=1）")
        print("[解决方案]")
        print("  1. 先在控制台创建应用（应用类型选择【接口服务】），然后继续")
        print("  2. 或改用 Web 模板快速部署（零代码）")
        
        choice = ask_user(['create_app', 'switch_to_template', 'abort'])
        handle_choice(choice)
        
elif delivery_mode == 'web_template':
    valid_apps = [app for app in all_apps if app.get('appType') == 2]
    
    if not valid_apps:
        print("[阻塞] 没有可用于 Web 模板的应用（需要 appType=2）")
        # 提示创建或转换
```

### 输出

```yaml
app_validation:
  valid: true | false
  selected_app:
    appId: "xxx"
    appName: "xxx"
    appType: 1 | 2
    has_llm_capability: true | false
  reason: "错误原因（如果 valid=false）"
  action: "建议的修复动作"
```

**PASS 标志**: `valid=true` 且应用具备对话能力

**FAIL 处理**: 
- 提示用户应用类型不匹配
- 给出明确的解决方案（创建新应用/切换路径/选择其他应用）
- 阻塞进入 Phase 2，直到用户解决

---

## Phase 2 门禁调用代码

**前置条件**: Phase 1.4 应用类型检测已通过

**调用**: `avatar-preflight`

**流程**:
```javascript
// Phase 1.4: 应用类型检测（新增）
const appValidation = validateAppTypeForDelivery(deliveryMode, selectedApp);

if (!appValidation.valid) {
  // 应用类型不匹配，阻塞
  console.error(`[阻塞] ${appValidation.reason}`);
  console.log(`[详情] ${appValidation.detail}`);
  showSolutionsAndWait(appValidation.action);
  return 'blocked_by_app_type';
}

// Phase 2: 环境门禁（只有应用类型检测通过后才执行）
const preflightResult = await runSkill('avatar-preflight', {
  platform: detectedPlatform,
  appId: selectedApp.appId,
  workDir: projectRoot
});

if (!preflightResult.allPass) {
  // 展示失败项和修复建议
  // 提示用户修复后重试，或选择跳过（风险提示）
  return askUserToFixOrSkip(preflightResult.failures);
}

// 全部 PASS，保存环境配置到 dev-env.yaml
saveDevEnv(preflightResult.config);
```

**输出**: 应用类型已验证 + 环境配置已验证并缓存

---

## SDK 集成陷阱检查（避免 native 库版本冲突）

**检查时机**: Phase 1 工程扫描阶段，对比 demo 工程结构时

### 正确的 libs 目录结构

✅ **正确**（参考官方 demo）:
```
app/libs/
├── avatar-core-v3.2.7.aar
└── xrtcsdk-5.2024.3.0.aar
```

❌ **错误**（会导致编译警告 + 运行时 native crash）:
```
app/libs/
├── avatar-core-v3.2.7.aar
├── xrtcsdk-5.2024.3.0.aar
├── arm64-v8a/
│   └── libjingle_peerconnection_so.so  ← 多余！与 aar 内版本冲突
└── armeabi-v7a/
    └── libjingle_peerconnection_so.so  ← 多余！
```

### 集成规则

扫描 demo 工程时，**只应复制 .aar 文件到新工程 app/libs/**，不复制任何散装 .so 文件。

**根因**:
- `avatar-core-v3.2.7.aar` 和 `xrtcsdk.aar` 内部已打包全部 native 库
- 包括 `libjingle_peerconnection_so.so` / `libxrtc.so` / `libiRTCEngine.so` / `libijkffmpeg.so` 等
- 手动复制 SDK 解压包里的 `webrtc/arm64-v8a/*.so` 会导致版本冲突
- AGP 会优先选择 app 模块的散装 .so，与 aar 内其他 native 库版本不匹配
- XRTC 初始化时 JNI 符号找不到或 ABI 不兼容，触发 native crash

### 编译警告信号

如果编译时出现以下警告，说明有重复的 native 库：
```
2 files found for path 'lib/arm64-v8a/libjingle_peerconnection_so.so'.
This version of the Android Gradle Plugin chooses the file from the app or dynamic-feature module,
but this can cause unexpected behavior or errors at runtime.
```

**处理方式**: 立即检查并删除 `app/libs/arm64-v8a/` 和 `app/libs/armeabi-v7a/` 目录。

### Phase 1 扫描增强逻辑

```python
def scan_demo_libs(demo_path, target_path):
    """扫描 demo 的 libs 目录，只复制 aar，过滤散装 .so"""
    demo_libs = f"{demo_path}/app/libs"
    target_libs = f"{target_path}/app/libs"
    
    # 1. 复制 .aar 文件
    for aar_file in glob(f"{demo_libs}/*.aar"):
        shutil.copy(aar_file, target_libs)
    
    # 2. 警告：若检测到散装 .so 目录
    if os.path.exists(f"{demo_libs}/arm64-v8a") or os.path.exists(f"{demo_libs}/armeabi-v7a"):
        log_warning(
            "检测到 demo 的 libs/ 目录含散装 native 库（arm64-v8a / armeabi-v7a）。"
            "这些库已被 aar 包含，不应单独复制，已自动过滤。"
        )
    
    # 3. 不复制散装 .so 目录
    # SKIP: arm64-v8a / armeabi-v7a / x86 / x86_64
```

### 用户提示

当从 demo 复制 SDK 文件时，提示用户：
```
✅ 已复制 SDK aar 文件到 app/libs/
⚠️  已过滤散装 native 库目录（aar 已包含，无需单独复制）

正确结构:
  app/libs/
  ├── avatar-core-v3.2.7.aar
  └── xrtcsdk-5.2024.3.0.aar

请勿手动添加 arm64-v8a / armeabi-v7a 目录。
```

