# Android 11+ 分区存储适配指南

**适用场景**: Android 应用日志保存路径配置

**问题**: Android 11 (API 30) 起启用分区存储（Scoped Storage），应用无法直接在 `/sdcard/` 根目录创建文件夹。

---

## 问题现象

### Demo 旧代码（不兼容 Android 11+）

```java
// AvatarConfig.java
public static final String LOG_PATH = "/sdcard/iflytek/log/";

// MainActivity.java
configBuilder.setLogSavePath(AvatarConfig.LOG_PATH);
```

**运行时错误**:
```
E AVATAR_LogFileWriter: LogFileWriter ErrorMessage:/sdcard/iflytek/log/avatarLog-*.txt: 
  open failed: ENOENT (No such file or directory)
```

---

## 解决方案

### 方案 A: 使用应用私有目录（推荐）

```java
// MainActivity.java
String logPath = null;
try {
    logPath = getExternalFilesDir(null).getAbsolutePath() + "/log/";
} catch (Exception e) {
    Log.e("AVATAR", "获取日志目录失败，使用默认路径", e);
}
configBuilder.setLogSavePath(logPath);
```

**路径示例**: `/storage/emulated/0/Android/data/com.your.package/files/log/`

**优势**:
- 无需额外权限（不需要 READ/WRITE_EXTERNAL_STORAGE）
- 兼容 Android 11+ 分区存储
- 应用卸载时自动清理

### 方案 B: AvatarConfig 设为 null（SDK 默认路径）

```java
// AvatarConfig.java
public class AvatarConfig {
    // 日志路径：null 让 SDK 使用内部默认路径
    public static final String LOG_PATH = null;
}

// MainActivity.java
configBuilder.setLogSavePath(AvatarConfig.LOG_PATH);  // 传 null
```

SDK 会使用内部默认路径（通常也是应用私有目录）。

---

## avatar-executing 生成规则

### AvatarConfig.java 生成模板

```java
package com.your.package;

public class AvatarConfig {
    public static final String APP_ID     = BuildConfig.AVATAR_APP_ID;
    public static final String API_KEY    = BuildConfig.AVATAR_API_KEY;
    public static final String API_SECRET = BuildConfig.AVATAR_API_SECRET;
    public static final String SCENE_ID   = BuildConfig.AVATAR_SCENE_ID;
    public static final String AVATAR_ID  = BuildConfig.AVATAR_AVATAR_ID;
    public static final String VCN        = BuildConfig.AVATAR_VCN;

    public static final String SERVER_URL = "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact";
    public static final String PROTOCOL = "xrtc";
    public static final int VIDEO_WIDTH = 720;
    public static final int VIDEO_HEIGHT = 1280;

    // 日志路径：null 让 SDK 使用默认路径，或在 MainActivity 中动态获取
    // ⚠️ 不要硬编码 /sdcard/ 路径（Android 11+ 不兼容）
    public static final String LOG_PATH = null;
}
```

### MainActivity.java initSDK() 生成模板

```java
private void initSDK() {
    AvatarPlatformConfig.Builder configBuilder = new AvatarPlatformConfig.Builder();
    
    // 日志路径：Android 11+ 分区存储适配
    String logPath = null;
    try {
        logPath = getExternalFilesDir(null).getAbsolutePath() + "/log/";
    } catch (Exception e) {
        appendLog("获取日志目录失败，使用默认路径");
    }

    configBuilder
            .setAppId(currentConfig.appId)
            .setApikey(currentConfig.apiKey)
            .setApiSecret(currentConfig.apiSecret)
            .setServerUrl(AvatarConfig.SERVER_URL)
            .setLogLevel(LogLevel.VERBOSE)
            .setLoggingPre("AVATAR_")
            .setLogSavePath(logPath)  // 动态获取的路径或 null
            .setUid("avatar_demo_user");

    AvatarPlatform.initialize(this, configBuilder.build(), new AvatarPlatform.IInitListener() {
        @Override
        public void onResult(String code, String desc) {
            if (AvatarError.SUCCESS.getErrorCode().equals(code)) {
                setupAvatar();
            } else {
                appendLog("SDK 初始化失败: " + code + " " + desc);
            }
        }
    });
}
```

---

## 兼容性检查

### avatar-preflight 集成

在 Layer 3.2 (Android 平台 SDK 依赖检查) 时，检查生成的代码是否包含：

1. **AvatarConfig.LOG_PATH 不应硬编码 `/sdcard/` 路径**
2. **MainActivity 应使用 `getExternalFilesDir()` 动态获取路径**
3. **目标 API Level >= 30 时强制检查**

### 检查脚本示例

```python
def check_log_path_compatibility(project_path, target_api_level):
    """检查日志路径是否兼容 Android 11+"""
    
    # 读取 AvatarConfig.java
    config_file = f"{project_path}/app/src/main/java/.../AvatarConfig.java"
    with open(config_file) as f:
        content = f.read()
    
    # 检测硬编码的 /sdcard/ 路径
    if target_api_level >= 30 and "/sdcard/" in content:
        return {
            "status": "fail",
            "message": "检测到硬编码 /sdcard/ 路径，Android 11+ 不兼容",
            "fix": "改用 getExternalFilesDir() 或设为 null"
        }
    
    return {"status": "pass"}
```

---

## 用户提示

当检测到目标 API Level >= 30 时，在生成代码后提示：

```
✅ 代码已生成

Android 11+ 分区存储适配:
  - ✅ 日志路径使用应用私有目录（getExternalFilesDir()）
  - ✅ 无需 READ/WRITE_EXTERNAL_STORAGE 权限
  - ✅ 兼容 Android 11+ 分区存储限制

日志路径示例: /storage/emulated/0/Android/data/com.your.package/files/log/
应用卸载时自动清理，无需手动管理。
```

