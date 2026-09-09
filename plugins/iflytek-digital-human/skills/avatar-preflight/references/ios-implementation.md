# Layer 3.3: iOS 平台 SDK 依赖检查

## Step 3.3.1: Framework 检查

**检查项**:
```
必需文件:
  - AvatarSDK.framework
  - XRTCSDK.framework (使用 XRTC 协议时)

必需配置:
  - Embed & Sign (动态库必须嵌入并签名)
```

**检查方式**:
```bash
# 1. 扫描 Framework
find . -name "AvatarSDK.framework" -o -name "XRTCSDK.framework"

# 2. 检查 Xcode 工程配置
# 读取 project.pbxproj，检查 Embed Frameworks 配置
```

**PASS 标志**: Framework 存在且配置为 Embed & Sign
**FAIL 处理**: 
```
Framework 缺失 → 提供下载链接
未配置 Embed & Sign → 提示在 Xcode 中设置:
  Target → General → Frameworks, Libraries, and Embedded Content
  → 设置为 "Embed & Sign"
```

---

## Step 3.3.2: Info.plist 权限检查

**检查项**:
```xml
<!-- Info.plist -->

<!-- 使用录音时必需 -->
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>
```

**检查方式**: 读取并解析 `Info.plist`

**PASS 标志**: 必需权限已配置
**FAIL 处理**: 生成需要添加的配置
```xml
<!-- 请在 Info.plist 中添加: -->
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>
```

---

## Step 3.3.3: 签名配置检查

**检查项**:
```yaml
必需配置:
  - Bundle ID 已配置
  - Team 已选择
  - Bitcode 已关闭 (SDK 不支持)
```

**检查方式**: 
```bash
# 读取 project.pbxproj
# 检查 PRODUCT_BUNDLE_IDENTIFIER
# 检查 DEVELOPMENT_TEAM
# 检查 ENABLE_BITCODE = NO
```

**PASS 标志**: 签名配置完整
**FAIL 处理**: 逐项提示配置步骤
```
Bundle ID 未配置 → 在 Xcode 中设置: Target → General → Identity
Team 未选择 → 在 Xcode 中设置: Target → Signing & Capabilities
Bitcode 未关闭 → Build Settings → Enable Bitcode → No
```

---

## iOS 工具链验证（Layer 5.2）

**调用**: `avatar-toolchain`（platform=ios，读 references/ios-checks.md）

**检查项**:
```bash
# 1. Xcode 已安装
xcode-select -p

# 2. CocoaPods 已安装（如使用）
pod --version

# 3. 签名证书有效
security find-identity -p codesigning
```

**PASS 标志**: 工具链完整
**FAIL 处理**: 提示安装或更新工具

---

## iOS 最小验证（Layer 6）

**生成内容**:
```
iOS:
  - 最小 ViewController
  - 初始化 SDK
  - 启动虚拟人
```

**执行验证**:
```bash
# 编译最小示例（需在 Mac 上）
xcodebuild -scheme AvatarDemo -configuration Debug

# 或提示用户在 Xcode 中运行
```

**关键事件序列**:
```
1. SDK 初始化成功: initializeConfig 返回 isSuccess=YES
2. WebSocket 连接成功: 收到 SDKEvents.connected 或类似事件
3. 收到 stream_start: 云端开始推流
4. 播放器首帧渲染: avatarOnEvent(FIRST_FRAME)
```
