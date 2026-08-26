# Android SDK 集成指南

**适用场景**: 

该文档不符合要求。已遗弃。详情请看：avatar-executing/references/android-sdk-build-playbook.md` 为唯一权威流程





> ⚠️ **权威性说明（必读）**：本文件为**速览参考**，API 签名以 `avatar-core-v3.2.7.aar` 反编译为准。
> **从零自建 Android 工程时，必须以 `avatar-executing/references/android-sdk-build-playbook.md` 为唯一权威流程**
> （HARD-GATE，含真实 API 全表、六步流程、字段锁定、编译性能配置、真机验证清单）。
> 本文件下述代码已按真实 API 校正；若与 AAR 反编译结果不符，一律以 AAR 为准。

---

## 一、SDK 文件

### 必需文件

```
app/libs/
├── avatar-core-v3.2.7.aar          # 核心 SDK
└── xrtcsdk-5.2024.3.0.aar          # XRTC 视频流 SDK
```

### 自动下载

使用 `avatar-artifact-download` skill 自动下载：

```
platform: android
target_dir: app/libs/
```

### 验证

```bash
ls app/libs/*.aar
# 应该看到两个 aar 文件
```

---

## 二、核心 API

### 2.1 初始化平台

```java
// MainActivity.java

// Step 1: 构建配置
AvatarPlatformConfig config = new AvatarPlatformConfig.Builder()
    .setAppId(APP_ID)
    .setApikey(API_KEY)
    .setApiSecret(API_SECRET)
    .setServerUrl("wss://avatar.cn-huadong-1.xf-yun.com/v1/interact")
    .setLogLevel(LogLevel.VERBOSE)
    .setLogPath(getExternalFilesDir(null).getAbsolutePath() + "/avatar_logs/")
    .setUid("user_unique_id")
    .build();

// Step 2: 初始化 SDK（3 参，结果走 IInitListener.onResult，成功 code="0"）
AvatarPlatform.initialize(getApplicationContext(), config, (code, msg) -> {
    if ("0".equals(code)) {
        // 成功：切主线程后 getController + 配参 + start
    } else {
        Log.e(TAG, "初始化失败 code=" + code + " " + msg);
    }
});

// Step 3: 获取控制器
AvatarPlayController controller = AvatarPlatform.getController();
```

### 2.2 创建视频播放器

```java
// Step 1: 在布局中准备容器（FrameLayout / ViewGroup）
android.view.ViewGroup videoContainer = findViewById(R.id.video_container);

// Step 2: 创建播放器（第二参是流模式字符串，非 View）
IStreamPlayer streamPlayer = StreamPlayerFactory.createPlayer(this, AvatarConstant.STREAM_XRTC);

// Step 3: 把容器交给播放器渲染，再设置到控制器（内部自动 bindAvatar + setAvatarListener）
streamPlayer.setRenderArea(videoContainer);
controller.setStreamPlayer(streamPlayer);
```

### 2.3 设置全局参数

```java
AvatarParams params = new AvatarParams();

// 视频流配置
AvatarParams.Stream stream = new AvatarParams.Stream();
stream.setProtocol("xrtc");
stream.setFps(25);
stream.setBitrate(2000);
stream.setAlpha(0);  // 0=普通背景, 1=透明背景

// 形象配置（固定模板）
AvatarParams.Avatar avatar = new AvatarParams.Avatar();
avatar.setAvatarId("118801001");  // 固定使用标准形象
avatar.setWidth(720);
avatar.setHeight(1280);
avatar.setStream(stream);

// 发音人配置（vcn 必须用 auth-avatar 探测到的授权值，不要硬编码历史值）
AvatarParams.TTS tts = new AvatarParams.TTS();
tts.setVcn(VCN);  // 例：x4_lingxiaoqi_oral，取自 xfyun_interface.py auth-avatar <appId> 探测结果
tts.setSpeed(50);
tts.setPitch(50);
tts.setVolume(50);

// 场景配置
AvatarParams.Scene scene = new AvatarParams.Scene();
scene.setSceneId(SCENE_ID);

// 调度配置
AvatarParams.Dispatch dispatch = new AvatarParams.Dispatch();
dispatch.setInteractiveMode(0);  // 0=追加模式, 1=打断模式

params.setAvatar(avatar);
params.setTTS(tts);
params.setScene(scene);
params.setDispatch(dispatch);

controller.setGlobalParams(params);
```

### 2.4 注册事件监听

```java
// 接口是 IAvatarListener（不是 AvatarListener），仅 3 个方法
controller.addAvatarListener(new IAvatarListener() {
    @Override
    public void onResult(String type, byte[] data, String extra) {
        // type: "asr" / "nlp" (AvatarDataType.RESPONSE_*)
        // ⚠️ 文本在 extra 的 JSON, 不在 data 字节:
        //   nlp: extra={"answer":{"text":"..."},"index":N,"status":1|2,"request_id":"...","service":"docqa|openai"}
        //        status=1 中间片, status=2 结束; 同 request_id 分片按序累加
        //   asr: extra={"text":"..."}
        Log.d(TAG, "onResult type=" + type + " extra=" + extra);
    }

    @Override
    public void onEvent(String type, String value) {
        // 状态事件: frame_start / frame_end / tts_duration / audit_result ...
        Log.i(TAG, "onEvent " + type);
    }

    @Override
    public void onError(String code, String desc, String extra) {
        Log.e(TAG, "Error " + code + ": " + desc);
    }
});
```

### 2.5 启动虚拟人

```java
controller.start();
```

### 2.6 文本交互

```java
// 文本交互（走 NLP + 知识库）: writeText + TextParams.setNlp(true)
TextParams tp = new TextParams();
tp.setNlp(true);
controller.writeText("请介绍一下力量训练", tp);   // 答案在 onResult(type="nlp") 的 extra

// 文本驱动播报（不走 NLP）: writeText 默认 nlp=false
controller.writeText("欢迎使用健身虚拟人");        // 直接朗读

// 语音交互: AudioRecorder(16000) + setAudioRecorder（内部自动泵 PCM）
AudioRecorder recorder = new AudioRecorder(
    MediaRecorder.AudioSource.MIC, 16000, AudioFormat.ENCODING_PCM_16BIT, AudioFormat.CHANNEL_IN_MONO);
recorder.init();
AudioParams ap = new AudioParams(); ap.setNlp(true);
controller.setAudioRecorder(recorder, ap);
recorder.startRecord();   // 说话
recorder.stopRecord();    // 松手
```

### 2.7 停止和释放

```java
@Override
protected void onDestroy() {
    super.onDestroy();

    if (controller != null) {
        controller.stop();
        controller.destroy();      // 真实方法是 destroy()
    }

    if (streamPlayer != null) {
        streamPlayer.stopPlay(true);
    }
}
```

---

## 三、权限配置

### 3.1 AndroidManifest.xml

```xml
<!-- 网络权限（必需） -->
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>

<!-- 音频权限（语音交互必需） -->
<uses-permission android:name="android.permission.RECORD_AUDIO"/>

<!-- Android 12+ 蓝牙权限（XRTC 必需） -->
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>

<!-- 可选：日志记录 -->
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
    android:maxSdkVersion="32"/>
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"
    android:maxSdkVersion="32"/>
```

### 3.2 动态权限申请

```java
// 根据 Android 版本动态构建权限列表
List<String> permissions = new ArrayList<>();
permissions.add(Manifest.permission.RECORD_AUDIO);

if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
    permissions.add(Manifest.permission.BLUETOOTH_CONNECT);
}

// 申请权限
ActivityCompat.requestPermissions(
    this,
    permissions.toArray(new String[0]),
    REQUEST_CODE_PERMISSIONS
);
```

---

## 四、Gradle 配置

### 4.1 build.gradle (app)

```gradle
// JDK 17 场景: AGP 8.1.4 / Gradle 8.0.2 / compileSdk 34（JDK11 才用 AGP7.x/Gradle7.x）
android {
    namespace 'com.example.avatar'
    compileSdk 34
    defaultConfig {
        applicationId "com.example.avatar"
        minSdk 26          // SDK 支持下限之上; 目标 Android 12+
        targetSdk 34
        ndk { abiFilters 'arm64-v8a', 'armeabi-v7a' }
    }
    sourceSets { main { jniLibs.srcDirs = ['src/main/jniLibs', 'libs'] } }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    packagingOptions { jniLibs { useLegacyPackaging = true } }
}

dependencies {
    implementation fileTree(include: ['*.jar', '*.aar'], dir: 'libs')
    implementation 'com.squareup.okhttp3:okhttp:4.9.3'
    implementation 'com.google.code.gson:gson:2.8.9'
    implementation 'androidx.appcompat:appcompat:1.6.1'
}
```

### 4.2 gradle.properties（性能，必写——否则首次编译极慢）

```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configureondemand=true
android.useAndroidX=true
```

> 编译永远用 `gradlew`（复用 daemon），**严禁 `--no-daemon`**（会导致每次全量、极慢）。
> AAR 已自带全套 xrtc .so，**不要**再手动放 webrtc .so 到 jniLibs（会重复冲突）。

---

## 五、常见错误处理

### 5.1 错误码

| 错误码   | 含义           | 解决方案        |
| ----- | ------------ | ----------- |
| 10110 | appId 不存在    | 检查 appId 配置 |
| 10113 | apiSecret 错误 | 检查签名生成      |
| 10114 | sceneId 不存在  | 检查场景配置      |
| 10120 | avatarId 未授权 | 使用已授权的形象    |
| 20002 | 视频播放失败       | 检查播放器配置     |

### 5.2 常见问题

**Q: 黑屏无视频？**

- **最常见根因：渲染面未正确挂载**。必须 `streamPlayer.setRenderArea(容器ViewGroup)`，不要用 `getRenderView` 分支逻辑
- 检查 `StreamPlayerFactory.createPlayer(this, "xrtc")` 是否正确创建
- 检查容器 View 是否可见、有有效尺寸
- 查看日志 `onEvent type=frame_start` 是否触发（触发=已连接播报，仅渲染面问题）

**Q: 无法启动？**

- 检查网络权限
- 检查 API 凭据是否正确
- 查看日志中的错误信息

---

## 六、完整示例

完整的 MainActivity 示例见本指南第二节各步骤的代码。

关键要点（真实 API）：

1. ✅ `AvatarPlatform.initialize(ctx, config, IInitListener)` 3 参初始化，成功 code="0"
2. ✅ `StreamPlayerFactory.createPlayer(this, "xrtc")` + `setRenderArea(容器)` 创建并挂载播放器
3. ✅ `AvatarPlayController` 管理虚拟人；`setStreamPlayer` 内部自动 bindAvatar
4. ✅ 显式传已授权的 `avatarId` 和 `vcn`（如 118801001 / x4_lingxiaoqi_oral）
5. ✅ 注册 **`IAvatarListener`**（onResult/onEvent/onError）处理事件；nlp/asr 文本在 onResult 的 **extra JSON**
6. ✅ 交互 `writeText(text, TextParams.setNlp(true))`；播报 `writeText(text)`；语音 `setAudioRecorder(recorder, audioParams)`

**切勿**手写 WebSocket 协议代码，必须使用 SDK 提供的 API。
**从零自建工程请以 `avatar-executing/references/android-sdk-build-playbook.md` 为准。**

---

## 七、参考资料

- 官方文档：https://www.xfyun.cn/doc/avatar/Android_SDK_summary.html
- SDK 下载：使用 `avatar-artifact-download` skill
- 配置模板：本指南第 2.3 节
