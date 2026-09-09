# Layer 5: Android 工具链检查（优化版）

## 自动修复策略（三级处理）

工具链检查按依赖类型分级处理，避免不必要的流程中断：

### 🟢 Tier 1: 自动处理（不打断流程）

**适用项**: 虚拟人 SDK (avatar-core.aar / xrtcsdk.aar)

**处理方式**:
1. 调用 `avatar-artifact-download` skill 获取下载链接
2. 后台下载到 `app/libs/`，进度提示
3. 完成后自动继续流程

**无需换源**: SDK 由控制台 CDN 直接提供

---

### 🟡 Tier 2: 交互确认后自动安装

**适用项**:
- JDK 17（180MB，约 1 分钟，使用 winget）
- Gradle 7.5（150MB，约 30 秒，腾讯云镜像）
- Android SDK（135MB，约 2 分钟，官方 CDN）

**AskUserQuestion 交互**:
```yaml
question: "检测到以下工具缺失。我可以自动安装（约 4 分钟，占用 465MB 磁盘），或你自己手动安装。如何处理？"
header: "工具链安装"
multiSelect: false
options:
  - label: "自动安装全部（推荐）"
    description: "模型自动下载并配置 JDK 17 + Gradle 7.5 + Android SDK，无需手动操作。预计 4 分钟，占用 465MB。"
  
  - label: "只安装 JDK"
    description: "仅自动安装 JDK 17（180MB，1分钟，使用 winget），Gradle 和 SDK 我自己装或已有。"
  
  - label: "只安装 Gradle"
    description: "仅自动安装 Gradle 7.5（150MB，30秒，腾讯云镜像），JDK 和 SDK 我自己装或已有。"
  
  - label: "只安装 Android SDK"
    description: "仅自动安装 Android SDK（135MB，2分钟，官方 CDN），JDK 和 Gradle 我自己装或已有。"
  
  - label: "我自己手动安装"
    description: "给我安装文档和命令，我自己操作后回来继续。"
```

**JDK 17 自动安装脚本（使用 winget）**:
```powershell
# Windows 平台 - 使用 winget 包管理器（Windows 10 1809+ 内置）
Write-Host "JDK 17 安装中（使用 winget）..."
winget install --id Microsoft.OpenJDK.17 --silent --accept-package-agreements --accept-source-agreements

# 验证安装
$jdk_path = "C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"
if (Test-Path "$jdk_path\bin\java.exe") {
    Write-Host "✅ JDK 17 已安装到 $jdk_path"
    
    # 配置环境变量（用户级持久化）
    [Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk_path, "User")
    
    $current_path = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($current_path -notlike "*$jdk_path\bin*") {
        [Environment]::SetEnvironmentVariable("Path", "$jdk_path\bin;$current_path", "User")
    }
    
    # 验证版本
    & "$jdk_path\bin\java.exe" -version
} else {
    Write-Host "❌ JDK 17 安装失败，请检查 winget 是否可用"
}
```

**Gradle 自动安装脚本（国内镜像加速）**:
```powershell
# Windows 平台
$gradle_url = "https://mirrors.cloud.tencent.com/gradle/gradle-7.5-bin.zip"
$gradle_dest = "C:\Gradle"

New-Item -ItemType Directory -Force -Path $gradle_dest
Invoke-WebRequest -Uri $gradle_url -OutFile "$gradle_dest\gradle-7.5-bin.zip"
Expand-Archive -Path "$gradle_dest\gradle-7.5-bin.zip" -DestinationPath $gradle_dest -Force

# 验证
& "$gradle_dest\gradle-7.5\bin\gradle.bat" --version
```

**镜像源选择**:
- ✅ 腾讯云: `https://mirrors.cloud.tencent.com/gradle/gradle-7.5-bin.zip`（推荐）
- ✅ 阿里云: `https://mirrors.aliyun.com/gradle/gradle-7.5-bin.zip`（备用）
- ❌ 官方源: `https://services.gradle.org/distributions/gradle-7.5-bin.zip`（国内慢）

**Android SDK 自动安装脚本（自动接受 license）**:
```powershell
# Windows 平台
$clt_url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
$sdk_root = "C:\Android\Sdk"

# 下载并配置 cmdline-tools
New-Item -ItemType Directory -Force -Path "$sdk_root\cmdline-tools"
Invoke-WebRequest -Uri $clt_url -OutFile "$sdk_root\clt.zip"
Expand-Archive -Path "$sdk_root\clt.zip" -DestinationPath "$sdk_root\cmdline-tools\temp" -Force
Move-Item "$sdk_root\cmdline-tools\temp\cmdline-tools" "$sdk_root\cmdline-tools\latest"

# 自动接受 licenses（避免交互式确认）
New-Item -ItemType Directory -Force -Path "$sdk_root\licenses"
@"
24333f8a63b6825ea9c5514f83c2829b004d1fee
d56f5187479451eabf01fb78af6dfcb131a6481e
"@ | Out-File "$sdk_root\licenses\android-sdk-license" -Encoding ASCII

# 安装必需组件（仅 3 个，共 135MB）
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"
& "$sdk_root\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root=$sdk_root "platform-tools" "platforms;android-34" "build-tools;34.0.0"

# 配置环境变量
[Environment]::SetEnvironmentVariable("ANDROID_HOME", $sdk_root, "User")
[Environment]::SetEnvironmentVariable("ANDROID_SDK_ROOT", $sdk_root, "User")
```

**Android SDK 组件说明**:

我们只安装编译 Android 应用的**最小必需组件**（135MB），而不是完整 SDK（3GB+）。

**必需组件**:
- `platform-tools`: 包含 adb/fastboot（10MB）
- `platforms;android-34`: Android 14 SDK Platform（65MB）
- `build-tools;34.0.0`: 编译工具 aapt/dex/apksigner（60MB）

**不安装**（可选，按需安装）:
- ❌ 其他 API Level（android-33/32/31...）
- ❌ NDK（Native Development Kit，1GB+）
- ❌ 模拟器镜像（system-images，每个 500MB-1GB）
- ❌ Google Play Services / CMake / LLDB

---

### 🔴 Tier 3: 特殊情况降级处理

当 Tier 2 自动安装失败时，给用户手动安装文档。

**JDK 17 安装失败时**:
```markdown
winget 不可用或安装失败，请手动下载：
1. 下载地址: https://learn.microsoft.com/java/openjdk/download#openjdk-17
2. 运行安装包，按提示完成
3. 验证: 打开新终端，运行 `java -version`
```

**Gradle 安装失败时**:
```markdown
所有镜像源失败，请手动下载：
1. 下载: https://services.gradle.org/distributions/gradle-7.5-bin.zip
2. 解压到: C:\Gradle\gradle-7.5
3. 验证: 运行 C:\Gradle\gradle-7.5\bin\gradle.bat --version
```

**Android SDK 安装失败时**:
```markdown
cmdline-tools 下载失败，建议安装 Android Studio（包含完整 SDK）：
下载地址: https://developer.android.com/studio
```

---

## 执行流程示例

```python
def layer5_android_toolchain_check(project_path):
    """Layer 5: Android 工具链检查（优化版）"""
    
    # Step 1: 检测并分类
    auto_fixable = []       # Tier 1: SDK 文件
    confirm_required = []   # Tier 2: JDK / Gradle / Android SDK
    
    # 检查虚拟人 SDK
    if not check_aar_files(f"{project_path}/app/libs"):
        auto_fixable.append({"item": "虚拟人 SDK", "action": "download_via_mcp"})
    
    # 检查 JDK
    if not check_jdk_17():
        confirm_required.append({
            "item": "JDK 17",
            "size": "180MB",
            "time": "1min",
            "script": "install_jdk17_winget.ps1"
        })
    
    # 检查 Gradle
    if not check_gradle():
        confirm_required.append({
            "item": "Gradle 7.5",
            "size": "150MB",
            "time": "30s",
            "script": "install_gradle_mirror.ps1"
        })
    
    # 检查 Android SDK
    if not check_android_sdk():
        confirm_required.append({
            "item": "Android SDK",
            "size": "135MB",
            "time": "2min",
            "script": "install_android_sdk.ps1"
        })
    
    # Step 2: Tier 1 自动处理
    for item in auto_fixable:
        download_sdk_files(item)
    
    # Step 3: Tier 2 交互确认
    if confirm_required:
        user_choice = ask_user_auto_install_options(confirm_required)
        if user_choice != "manual":
            execute_auto_install(confirm_required, user_choice)
            return layer5_android_toolchain_check(project_path)  # 重新检查
        else:
            show_manual_install_guide(confirm_required)
            return {"status": "blocked"}
    
    # Step 4: 全部就绪
    return {"status": "pass"}
```

---

## Android 运行时权限依赖表（按 API Level 动态）

| 权限 | 必需场景 | 最低 API | 动态申请 | 说明 |
|------|----------|----------|----------|------|
| INTERNET | 所有 | 1 | 否 | 普通权限 |
| ACCESS_NETWORK_STATE | 所有 | 1 | 否 | 普通权限 |
| RECORD_AUDIO | 语音交互/全双工 | 23 | 是 | 危险权限 |
| **BLUETOOTH_CONNECT** | **XRTC 协议** | **31** | **是** | **⚠️ 隐蔽陷阱：XRTC SDK 初始化时检测蓝牙耳机，即使不使用也必需** |
| READ_EXTERNAL_STORAGE | 日志保存 | 23 | 是 | Android 13+ 废弃 |
| WRITE_EXTERNAL_STORAGE | 日志保存 | 23 | 是 | Android 13+ 废弃 |

### ⚠️ BLUETOOTH_CONNECT 权限（Android 12+ 强制必需）

**隐蔽陷阱详解**:
- XRTC SDK 初始化时会调用 `BluetoothAdapter.getProfileConnectionState()` 检测蓝牙耳机连接状态
- Android 12 (API 31) 起该 API 需要 `BLUETOOTH_CONNECT` 运行时权限
- **即使用户不使用蓝牙耳机，SDK 也会执行检测逻辑**，所以该权限是强制必需
- 缺失时抛出 `SecurityException: Need android.permission.BLUETOOTH_CONNECT`，导致应用崩溃

**崩溃栈示例**:
```
FATAL EXCEPTION: Thread-4
java.lang.SecurityException: Need android.permission.BLUETOOTH_CONNECT permission
  at android.bluetooth.IBluetooth$Stub$Proxy.getProfileConnectionState(IBluetooth.java:3617)
  at android.bluetooth.BluetoothAdapter.getProfileConnectionState(BluetoothAdapter.java:3088)
  at com.iflytek.xrtcsdk.basic.util.IXAudioUtil.isBluetoothHeadsetConnected(IXAudioUtil.java:2)
  at com.iflytek.xrtcsdk.basic.util.IXAudioManager.<init>(IXAudioManager.java:304)
  at com.iflytek.xrtcsdk.conference.impl.IXRTCCloudImpl.<init>(IXRTCCloudImpl.java:2615)
```

**Layer 2 检查增强规则**:
- 当检测到 `protocol=xrtc` 且目标设备 `API Level >= 31` 时
- 自动将 `BLUETOOTH_CONNECT` 加入必需权限清单
- 在 AndroidManifest.xml 声明检查和 PermissionHelper 动态申请中都要包含

**PermissionHelper 动态权限构建示例**:
```java
private static String[] buildRequiredPermissions() {
    List<String> perms = new ArrayList<>();
    perms.add(Manifest.permission.RECORD_AUDIO);

    // Android 13+ 废弃存储权限
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
        perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE);
        perms.add(Manifest.permission.READ_EXTERNAL_STORAGE);
    }

    // ⚠️ Android 12+ 必需蓝牙连接权限（XRTC 检测耳机）
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        perms.add(Manifest.permission.BLUETOOTH_CONNECT);
    }

    return perms.toArray(new String[0]);
}
```

---

## Layer 3.2: Android 平台 SDK 依赖检查

## Step 3.2.1: AAR 文件检查

**检查项**:
```
必需文件:
  - app/libs/avatar-core-v*.aar
  - app/libs/xrtcsdk-*.aar (使用 XRTC 协议时)
```

**检查方式**:
```bash
# 扫描 app/libs/ 目录
ls app/libs/*.aar 2>/dev/null

# 未找到时询问
AskUserQuestion:
  - 选项1: 指定 AAR 路径
  - 选项2: 自动下载到 app/libs/
  - 选项3: 稍后手动添加
```

**PASS 标志**: AAR 文件存在
**FAIL 处理**: 提供下载链接和保存路径建议
