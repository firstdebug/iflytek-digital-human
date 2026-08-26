# Layer 5: Android 工具链检查（优化版）

## 工具链检查

本层只检查契约目标 Android 工程的实际工具链和 SDK 产物。缺失项按契约授权处理：

- 已声明 `download_sdk`：使用插件根目录工具下载并校验 SDK。
- 未声明下载或安装类授权：将契约状态设为 `blocked`，记录缺失项和恢复条件，回到 Grill 更新并重新确认。
- 检查不得跳过，不提供执行阶段的安装选项问卷或独立出口。

检查项包括 JDK、Gradle、Android SDK、AAR、jniLibs、okhttp/gson、ABI 和签名配置。每一项以命令退出码和实际文件/版本为证据；通过后继续同一契约的 SDK 构建。

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

# 未找到时
  - 契约已授权 download_sdk：用平台工具下载并校验到目标工程
  - 未授权：状态设为 blocked，回到 Grill 更新并重新确认契约
```

**PASS 标志**: AAR 文件存在
**FAIL 处理**: 记录缺失产物和恢复条件；不得跳过 SDK 检查

