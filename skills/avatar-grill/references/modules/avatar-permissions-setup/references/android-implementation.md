# Android 平台权限实现

## 静态权限配置

```xml
<!-- AndroidManifest.xml -->

<!-- 必需权限 -->
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>

<!-- 录音权限（语音交互时必需） -->
<uses-permission android:name="android.permission.RECORD_AUDIO"/>

<!-- 可选权限 -->
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"
                 android:maxSdkVersion="32"/>  <!-- 保存日志时 -->
<uses-permission android:name="android.permission.CAMERA"/>  <!-- 视频通话时 -->
```

## 运行时权限申请

```java
// MainActivity.java

import android.Manifest;
import android.content.pm.PackageManager;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

public class MainActivity extends AppCompatActivity {
    
    private static final int REQUEST_RECORD_AUDIO = 1;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // 检查并申请麦克风权限
        checkAndRequestPermission();
    }
    
    private void checkAndRequestPermission() {
        // 1. 检查权限状态
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            
            // 2. 判断是否需要显示说明
            if (ActivityCompat.shouldShowRequestPermissionRationale(this, 
                    Manifest.permission.RECORD_AUDIO)) {
                // 显示对话框说明为什么需要权限
                showPermissionRationale();
            } else {
                // 直接申请权限
                ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.RECORD_AUDIO},
                    REQUEST_RECORD_AUDIO);
            }
        } else {
            // 权限已授予
            startVoiceInteraction();
        }
    }
    
    private void showPermissionRationale() {
        new AlertDialog.Builder(this)
            .setTitle("需要麦克风权限")
            .setMessage("虚拟人语音交互功能需要使用麦克风")
            .setPositiveButton("授予权限", (dialog, which) -> {
                ActivityCompat.requestPermissions(MainActivity.this,
                    new String[]{Manifest.permission.RECORD_AUDIO},
                    REQUEST_RECORD_AUDIO);
            })
            .setNegativeButton("取消", null)
            .show();
    }
    
    @Override
    public void onRequestPermissionsResult(int requestCode, 
                                          String[] permissions, 
                                          int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        
        if (requestCode == REQUEST_RECORD_AUDIO) {
            if (grantResults.length > 0 && 
                grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                // 权限授予成功
                startVoiceInteraction();
            } else {
                // 权限拒绝
                if (!ActivityCompat.shouldShowRequestPermissionRationale(this, 
                        Manifest.permission.RECORD_AUDIO)) {
                    // 用户选择了"不再询问"，引导到设置
                    showSettingsDialog();
                } else {
                    Toast.makeText(this, "没有麦克风权限，无法使用语音功能", 
                                 Toast.LENGTH_SHORT).show();
                }
            }
        }
    }
    
    private void showSettingsDialog() {
        new AlertDialog.Builder(this)
            .setTitle("需要麦克风权限")
            .setMessage("请在设置中开启麦克风权限")
            .setPositiveButton("去设置", (dialog, which) -> {
                Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                Uri uri = Uri.fromParts("package", getPackageName(), null);
                intent.setData(uri);
                startActivity(intent);
            })
            .setNegativeButton("取消", null)
            .show();
    }
    
    private void startVoiceInteraction() {
        // 启动语音交互
        Log.d(TAG, "权限已授予，开始语音交互");
    }
}
```

## 问题诊断: Android 运行时崩溃（RECORD_AUDIO）

**原因**: 
- AndroidManifest.xml 未声明权限
- 运行时未申请权限
- targetSdkVersion >= 23 但未处理运行时权限

**解决**:
```xml
<!-- 1. 静态声明 -->
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
```

```java
// 2. 运行时申请
if (ContextCompat.checkSelfPermission(this, RECORD_AUDIO) != GRANTED) {
    ActivityCompat.requestPermissions(this, new String[]{RECORD_AUDIO}, 1);
}
```

**验证**:
```bash
# 查看应用权限
adb shell dumpsys package com.your.package | grep permission
```

## 问题诊断: 用户"不再询问"后无法申请权限（Android）

```java
if (!ActivityCompat.shouldShowRequestPermissionRationale(this, permission)) {
    // 用户选择了"不再询问"，引导到设置
    Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
    Uri uri = Uri.fromParts("package", getPackageName(), null);
    intent.setData(uri);
    startActivity(intent);
}
```
