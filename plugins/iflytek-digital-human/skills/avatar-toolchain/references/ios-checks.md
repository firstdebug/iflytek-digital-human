# iOS 平台工具链检查

iOS 分支的检查项清单、检测代码、修复建议、编排流程与状态分类、输出格式、常见问题修复。
骨架与 `summarizeStatus` 通用实现见 `../SKILL.md`；本文件只承载 iOS 特定载荷。

---

## 检查项清单

| # | 检查项 | 重要性 | 说明 |
|---|--------|--------|------|
| 1 | Xcode 环境 | ⭐⭐⭐ 必需 | 安装与版本（≥12.0，荐 14.0+） |
| 2 | iOS Deployment Target | ⭐⭐⭐ 必需 | ≥11.0（SDK 要求） |
| 3 | CocoaPods（可选） | ⭐⭐ | 使用 Pods 管理依赖时 |
| 4 | Framework 嵌入配置 | ⭐⭐⭐ 必需 | Embed & Sign |
| 5 | 系统库依赖 | ⭐⭐ 必需 | libc++/SystemConfiguration/AVFoundation |
| 6 | Build Settings | ⭐⭐⭐ | Bitcode/arch/签名字段 |
| 7 | Info.plist 权限 | ⭐⭐⭐ | 录音功能时必需 |
| 8 | 签名配置 | ⭐⭐⭐ | 真机运行和发布必需 |

检查优先级：Xcode / Deployment Target / Framework = Critical；权限配置 = High（使用录音时）；
签名配置 = Medium（真机运行时）；CocoaPods = Low（可选）。

模拟器 vs 真机：模拟器不需要签名配置；真机需要证书和 Provisioning Profile；
Framework 架构需要支持真机（arm64）。

macOS 专属：iOS 开发只能在 macOS 上进行；真机运行和发布需要 Apple 开发者账号。

---

## 1. Xcode 环境

**重要性**: ⭐⭐⭐ 必需

**检查方法**:
```bash
# 1. 检查 Xcode 安装
xcode-select -p

# 2. 检查 Xcode 版本
xcodebuild -version
```

**要求**:
```yaml
required: true
minimum_version: "12.0"
recommended_version: "14.0+"
```

**判断**:
```javascript
try {
  const xcodePath = execSync('xcode-select -p').toString().trim();
  const xcodeVersion = execSync('xcodebuild -version').toString();
  const versionMatch = xcodeVersion.match(/Xcode (\d+\.\d+)/);
  
  if (!versionMatch) {
    return { status: 'not_found', fix: '安装 Xcode 14.0+' };
  }
  
  const version = parseFloat(versionMatch[1]);
  
  if (version >= 14.0) {
    return { status: 'optimal', version, path: xcodePath };
  } else if (version >= 12.0) {
    return { status: 'acceptable', version, path: xcodePath,
             note: '建议升级到 Xcode 14.0+' };
  } else {
    return { status: 'too_old', version,
             fix: '升级到 Xcode 12.0+' };
  }
} catch (err) {
  return { status: 'not_found', 
           fix: '从 App Store 安装 Xcode 或运行 xcode-select --install' };
}
```

**修复建议**:
```bash
# 1. 从 App Store 安装 Xcode
# 或下载: https://developer.apple.com/xcode/

# 2. 安装命令行工具
xcode-select --install

# 3. 设置 Xcode 路径
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
```

---

## 2. iOS Deployment Target

**重要性**: ⭐⭐⭐ 必需

**检查方法**: 读取 Xcode 工程配置

```javascript
// 方式 1: 读取 project.pbxproj
const projectFile = fs.readFileSync('*.xcodeproj/project.pbxproj', 'utf-8');
const deploymentMatch = projectFile.match(/IPHONEOS_DEPLOYMENT_TARGET = ([\d.]+)/);

// 方式 2: 使用 xcodebuild
const deploymentTarget = execSync(
  'xcodebuild -showBuildSettings | grep IPHONEOS_DEPLOYMENT_TARGET'
).toString();

if (deploymentMatch) {
  const version = parseFloat(deploymentMatch[1]);
  
  if (version < 11.0) {
    return {
      status: 'too_low',
      current: version,
      required: 11.0,
      fix: 'Target → General → Deployment Info → iOS 11.0+'
    };
  }
  
  return { status: 'ok', version };
}
```

**要求**:
```yaml
minimum_version: "11.0"  # 虚拟人 SDK 要求
recommended_version: "13.0+"
```

**修复建议**:
```
在 Xcode 中:
1. 选择 Target
2. General → Deployment Info
3. iOS Deployment Target 设置为 11.0 或更高
```

---

## 3. CocoaPods 环境（可选）

**重要性**: ⭐⭐ 使用 Pods 管理依赖时必需

**检查方法**:
```bash
# 1. 检查 CocoaPods 安装
pod --version

# 2. 检查 Podfile 是否存在
ls Podfile
```

**要求**:
```yaml
required: false  # 手动引入 Framework 时不需要
minimum_version: "1.10.0"
recommended_version: "1.12.0+"
```

**判断**:
```javascript
const hasPodfile = fs.existsSync('Podfile');

if (!hasPodfile) {
  return {
    status: 'not_using_pods',
    note: '项目未使用 CocoaPods，手动管理 Framework'
  };
}

try {
  const podVersion = execSync('pod --version').toString().trim();
  const version = parseFloat(podVersion);
  
  if (version >= 1.12) {
    return { status: 'optimal', version };
  } else if (version >= 1.10) {
    return { status: 'acceptable', version,
             note: '建议升级到 CocoaPods 1.12+' };
  } else {
    return { status: 'outdated', version,
             fix: 'sudo gem install cocoapods' };
  }
} catch (err) {
  return {
    status: 'not_found',
    fix: 'sudo gem install cocoapods'
  };
}
```

**修复建议**:
```bash
# 安装 CocoaPods
sudo gem install cocoapods

# 初始化 Pods
pod setup

# 安装依赖
pod install
```

---

## 4. Framework 嵌入配置检查

**重要性**: ⭐⭐⭐ 必需

**检查方法**: 读取 project.pbxproj

```javascript
const projectFile = fs.readFileSync('*.xcodeproj/project.pbxproj', 'utf-8');

// 检查 Framework 是否存在
const frameworks = ['AvatarSDK.framework', 'XRTCSDK.framework'];
const embeddedFrameworks = [];
const missingFrameworks = [];

for (const framework of frameworks) {
  if (projectFile.includes(framework)) {
    // 检查是否配置为 Embed & Sign
    const embedPattern = new RegExp(`${framework}.*ATTRIBUTES.*=.*\\(.*CodeSignOnCopy.*\\)`);
    
    if (projectFile.match(embedPattern)) {
      embeddedFrameworks.push({ name: framework, embedded: true });
    } else {
      embeddedFrameworks.push({ 
        name: framework, 
        embedded: false,
        fix: 'Target → General → Frameworks → 设置为 Embed & Sign'
      });
    }
  } else {
    missingFrameworks.push(framework);
  }
}

if (missingFrameworks.length > 0) {
  return {
    status: 'frameworks_missing',
    missing: missingFrameworks,
    fix: '拖拽 Framework 到 Xcode 工程'
  };
}

const notEmbedded = embeddedFrameworks.filter(f => !f.embedded);
if (notEmbedded.length > 0) {
  return {
    status: 'not_embedded',
    frameworks: notEmbedded,
    fix: 'Target → General → Frameworks → 设置为 Embed & Sign'
  };
}

return { status: 'frameworks_ok', frameworks: embeddedFrameworks };
```

**要求**:
```yaml
required_frameworks:
  - AvatarSDK.framework
  - XRTCSDK.framework  # 使用 XRTC 协议时
embed_mode: "Embed & Sign"  # 动态库必须嵌入
```

**修复建议**:
```
在 Xcode 中:
1. Target → General → Frameworks, Libraries, and Embedded Content
2. 点击 + 添加 Framework
3. 设置为 "Embed & Sign"

或手动拖拽:
1. 拖拽 .framework 到 Xcode 工程
2. 勾选 "Copy items if needed"
3. 设置 Embed & Sign
```

---

## 5. 系统库依赖检查

**重要性**: ⭐⭐ 必需

**检查方法**: 读取 project.pbxproj

```javascript
const projectFile = fs.readFileSync('*.xcodeproj/project.pbxproj', 'utf-8');

const requiredLibs = [
  'libc++.tbd',
  'SystemConfiguration.framework',  // 网络状态检测
  'AVFoundation.framework'           // 音视频
];

const missingLibs = [];

for (const lib of requiredLibs) {
  if (!projectFile.includes(lib)) {
    missingLibs.push(lib);
  }
}

if (missingLibs.length > 0) {
  return {
    status: 'missing_system_libs',
    missing: missingLibs,
    fix: 'Target → Build Phases → Link Binary With Libraries → 添加系统库'
  };
}

return { status: 'system_libs_ok' };
```

**修复建议**:
```
在 Xcode 中:
1. Target → Build Phases → Link Binary With Libraries
2. 点击 + 添加系统库:
   - libc++.tbd
   - SystemConfiguration.framework
   - AVFoundation.framework
```

---

## 6. Build Settings 检查

**重要性**: ⭐⭐⭐ 影响编译和运行

**检查方法**: 使用 xcodebuild

```bash
xcodebuild -showBuildSettings | grep "ENABLE_BITCODE\|VALID_ARCHS\|OTHER_LDFLAGS"
```

**关键配置**:
```javascript
const buildSettings = execSync('xcodebuild -showBuildSettings').toString();

const checks = {
  bitcode: {
    key: 'ENABLE_BITCODE',
    expected: 'NO',
    reason: '虚拟人 SDK 不支持 Bitcode'
  },
  
  archs: {
    key: 'VALID_ARCHS',
    expected: 'arm64',
    reason: 'iOS 11+ 仅支持 arm64'
  },
  
  bundle_id: {
    key: 'PRODUCT_BUNDLE_IDENTIFIER',
    required: true,
    reason: '签名必需'
  },
  
  team: {
    key: 'DEVELOPMENT_TEAM',
    required: true,
    reason: '签名必需'
  }
};

const issues = [];

for (const [name, check] of Object.entries(checks)) {
  const match = buildSettings.match(new RegExp(`${check.key} = (.+)`));
  
  if (!match) {
    if (check.required) {
      issues.push({
        setting: check.key,
        issue: '未配置',
        fix: check.reason
      });
    }
  } else if (check.expected && match[1].trim() !== check.expected) {
    issues.push({
      setting: check.key,
      current: match[1].trim(),
      expected: check.expected,
      reason: check.reason
    });
  }
}

if (issues.length > 0) {
  return { status: 'build_settings_issues', issues };
}

return { status: 'build_settings_ok' };
```

**推荐配置**:
```
Build Settings:
- Enable Bitcode: NO
- Valid Architectures: arm64
- Bundle Identifier: com.your.app
- Development Team: Your Team ID
```

---

## 7. Info.plist 权限配置检查

**重要性**: ⭐⭐⭐ 使用录音功能时必需

**检查方法**: 读取 Info.plist

```javascript
const plist = require('plist');
const infoPlist = plist.parse(fs.readFileSync('Info.plist', 'utf-8'));

const requiredPermissions = {
  'NSMicrophoneUsageDescription': {
    required: true,  // 使用录音时
    purpose: '语音交互功能',
    example: '用于虚拟人语音交互'
  },
  
  'NSCameraUsageDescription': {
    required: false,
    purpose: '摄像头功能（如需）',
    example: '用于视频通话'
  }
};

const missingPermissions = [];

for (const [key, perm] of Object.entries(requiredPermissions)) {
  if (perm.required && !infoPlist[key]) {
    missingPermissions.push({
      key,
      purpose: perm.purpose,
      example: perm.example
    });
  }
}

if (missingPermissions.length > 0) {
  return {
    status: 'missing_permissions',
    missing: missingPermissions,
    fix: '在 Info.plist 中添加权限说明'
  };
}

return { status: 'permissions_ok' };
```

**修复建议**:
```xml
<!-- Info.plist -->

<!-- 麦克风权限（使用录音时必需） -->
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>

<!-- 摄像头权限（可选） -->
<key>NSCameraUsageDescription</key>
<string>用于视频通话</string>
```

---

## 8. 签名配置检查

**重要性**: ⭐⭐⭐ 真机运行和发布必需

**检查方法**: 使用 security 命令

```bash
# 1. 检查证书
security find-identity -p codesigning

# 2. 检查 Provisioning Profile
ls ~/Library/MobileDevice/Provisioning\ Profiles/
```

**判断**:
```javascript
try {
  const identities = execSync('security find-identity -p codesigning').toString();
  const validIdentities = identities.match(/\d+\) [A-F0-9]{40} "(.+?)"/g);
  
  if (!validIdentities || validIdentities.length === 0) {
    return {
      status: 'no_certificates',
      fix: '在 Xcode → Preferences → Accounts 中下载证书'
    };
  }
  
  // 检查 Bundle ID 和 Team 是否配置
  const buildSettings = execSync('xcodebuild -showBuildSettings').toString();
  const bundleId = buildSettings.match(/PRODUCT_BUNDLE_IDENTIFIER = (.+)/);
  const team = buildSettings.match(/DEVELOPMENT_TEAM = (.+)/);
  
  if (!bundleId || !team) {
    return {
      status: 'signing_not_configured',
      fix: 'Target → Signing & Capabilities → 配置 Team 和 Bundle ID'
    };
  }
  
  return {
    status: 'signing_ok',
    certificates: validIdentities.length,
    bundleId: bundleId[1].trim(),
    team: team[1].trim()
  };
} catch (err) {
  return {
    status: 'signing_error',
    error: err.message,
    fix: '检查 Xcode 签名配置'
  };
}
```

**修复建议**:
```
在 Xcode 中:
1. Xcode → Preferences → Accounts
   - 添加 Apple ID
   - 下载证书

2. Target → Signing & Capabilities
   - 选择 Team
   - 配置 Bundle Identifier
   - 勾选 Automatically manage signing

3. 真机运行:
   - 连接设备
   - 信任开发者（设置 → 通用 → 设备管理）
```

---

## 完整检查流程（编排）

```javascript
async function checkIOSToolchain() {
  const results = {
    platform: 'ios',
    checks: {}
  };
  
  // 1. Xcode 环境
  results.checks.xcode = await checkXcode();
  
  // 2. iOS Deployment Target
  results.checks.deployment_target = await checkDeploymentTarget();
  
  // 3. CocoaPods（可选）
  results.checks.cocoapods = await checkCocoaPods();
  
  // 4. Framework 嵌入配置
  results.checks.frameworks = await checkFrameworks();
  
  // 5. 系统库依赖
  results.checks.system_libs = await checkSystemLibs();
  
  // 6. Build Settings
  results.checks.build_settings = await checkBuildSettings();
  
  // 7. Info.plist 权限
  results.checks.permissions = await checkPermissions();
  
  // 8. 签名配置
  results.checks.signing = await checkSigning();
  
  // 汇总状态（summarizeStatus 通用骨架见 ../SKILL.md）
  results.status = summarizeStatus(results.checks);
  
  return results;
}
```

## 状态分类（填入通用 summarizeStatus）

iOS 分支在通用 `summarizeStatus` 骨架的「平台特定分类规则」处填入：

```javascript
// Xcode 未安装
if (checks.xcode.status === 'not_found') {
  critical.push('Xcode 未安装');
}

// Deployment Target 过低
if (checks.deployment_target.status === 'too_low') {
  critical.push('iOS Deployment Target < 11.0');
}

// Framework 缺失或未嵌入
if (checks.frameworks.status === 'frameworks_missing') {
  critical.push('Framework 缺失');
} else if (checks.frameworks.status === 'not_embedded') {
  critical.push('Framework 未设置 Embed & Sign');
}

// 权限配置缺失
if (checks.permissions.status === 'missing_permissions') {
  warnings.push('Info.plist 缺少权限说明');
}

// 签名未配置
if (checks.signing.status === 'no_certificates') {
  warnings.push('证书未安装');
} else if (checks.signing.status === 'signing_not_configured') {
  warnings.push('签名未配置');
}

// Build Settings 问题
if (checks.build_settings.status === 'build_settings_issues') {
  warnings.push('Build Settings 配置有误');
}
```

HARD-GATE：macOS 专属；Deployment Target ≥ 11.0（低于判 critical，SDK 无法运行）；
Framework 必须 `Embed & Sign`（未嵌入导致 `dyld: Library not loaded`，critical）；
`Enable Bitcode = NO`（SDK 不支持 Bitcode）；`VALID_ARCHS = arm64`（iOS 11+ 仅支持 arm64）；
录音功能必须配置 `NSMicrophoneUsageDescription`（缺失运行时崩溃）。

Red Flags（判定为 critical_issues）：Xcode 未安装（`status: not_found`）；
iOS Deployment Target < 11.0；Framework 缺失或未设置 Embed & Sign。

---

## 输出格式

### 成功输出
```yaml
status: "all_ok"
platform: "ios"
checks:
  xcode:
    status: "optimal"
    version: 14.3
  deployment_target:
    status: "ok"
    version: 13.0
  frameworks:
    status: "frameworks_ok"
    frameworks:
      - name: "AvatarSDK.framework"
        embedded: true
      - name: "XRTCSDK.framework"
        embedded: true
  permissions:
    status: "permissions_ok"
  signing:
    status: "signing_ok"
    certificates: 2
```

### 关键问题输出
```yaml
status: "critical_issues"
issues:
  - "Framework 未设置 Embed & Sign"
  - "iOS Deployment Target < 11.0"
checks:
  frameworks:
    status: "not_embedded"
    frameworks:
      - name: "AvatarSDK.framework"
        embedded: false
        fix: "Target → General → Frameworks → 设置为 Embed & Sign"
  deployment_target:
    status: "too_low"
    current: 9.0
    required: 11.0
    fix: "Target → General → Deployment Info → iOS 11.0+"
```

---

## 常见问题修复

### 1. Framework 加载失败 (dyld: Library not loaded)

**原因**: Framework 未设置 Embed & Sign

**解决**:
```
Target → General → Frameworks, Libraries, and Embedded Content
→ 设置为 "Embed & Sign"
```

### 2. 真机运行签名失败

**原因**: 
- Bundle ID 冲突
- Team 未选择
- 证书过期

**解决**:
```
1. 修改 Bundle Identifier 为唯一值
2. Target → Signing & Capabilities → 选择 Team
3. Xcode → Preferences → Accounts → 更新证书
```

### 3. Bitcode 编译错误

**原因**: 虚拟人 SDK 不支持 Bitcode

**解决**:
```
Build Settings → Enable Bitcode → NO
```

### 4. 录音权限崩溃

**原因**: Info.plist 未配置 NSMicrophoneUsageDescription

**解决**:
```xml
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>
```

