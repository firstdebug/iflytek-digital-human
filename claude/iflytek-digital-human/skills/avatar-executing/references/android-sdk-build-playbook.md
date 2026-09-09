# Android SDK 构建 Playbook（HARD-GATE 强制流程）

> **适用**：用户要求"用 SDK 自建 Android 虚拟人工程"（原生 App，非 Web 模板、非直播）。
> **原则**：本文件是 Android SDK 自建工程的**唯一权威落地流程**。按此流程生成的代码必须**一次编译成功、一次真机跑通**，
> 不允许"先生成、再靠报错逐个打补丁"，更不允许照 `integration-guides/android.md` 的简化 API 写代码。
> 所有 API 签名来自 **`avatar-core-v3.2.7.aar` 真实反编译（javap）**，已在真机 `10AF9T1AG3002EK` 验证跑通。

---

## 0. 为什么需要这个 Playbook（血泪根因）

`integration-guides/android.md` 是**人工简化版文档，与真实 SDK API 不符**。照它写的代码会编译失败或运行崩溃，
且反编译 AAR 才能拿到真 API 耗费大量轮次。下面是"文档写的 vs 真实的"对照（**一律以本表真实列为准**）：

| 环节 | ❌ 简化文档写的（不存在/错误） | ✅ 真实 API（avatar-core-v3.2.7 反编译） |
|------|------------------------------|----------------------------------------|
| 包名 | 裸类名，未给 import | 统一 `com.iflytek.avalibrary.*` |
| 初始化 | `AvatarPlatform.initialize(ctx, config)` 返回 AvatarError | `AvatarPlatform.initialize(Context, config, IInitListener)` **3参**，结果走 `IInitListener.onResult(code,msg)`，成功 **code="0"** |
| Builder | `.setApiKey()` | `.setApikey()` **小写 k** |
| 播放器 | `StreamPlayerFactory.createStreamPlayer(ctx, View)` | `StreamPlayerFactory.createPlayer(Context, String streamMode)`，再 `IStreamPlayer.setRenderArea(容器ViewGroup)` |
| 监听器 | `AvatarListener{ onAvatarReady/onNlpResult/onAsrResult }` | 接口是 **`IAvatarListener`**，仅 `onResult(type,byte[],extra)` / `onEvent(type,value)` / `onError(code,desc,extra)` |
| 文本交互 | `controller.sendText(text)` | **`controller.writeText(text, TextParams)`**，`TextParams.setNlp(true)`=走NLP |
| 文本播报 | 同上/未区分 | `controller.writeText(text)` 默认 **mNlp=false=纯播报**（同名不同参，非独立方法） |
| 语音 | `startAudioInteract()/writeAudioFrame()` | `controller.setAudioRecorder(recorder, audioParams)`（内部自动泵PCM）+ `recorder.startRecord()/stopRecord()` |
| 响应文本 | 假设在 data 字节 | **在 `extra` 参数的 JSON（`answer.text`）**，data 常为空 |
| 字幕 | 假设有 subtitle 回调 | **无独立回调**，用 onResult 的 nlp/asr 文本渲染 |

**一句话铁律**：客户端 API **只认本 playbook §1**，不认 integration-guides/android.md、不猜、不臆造。
若怀疑 AAR 版本不同导致签名变化，用 `javap -public -classpath classes.jar com.iflytek.avalibrary.X` 核对，不要猜。

---

## 1. 真实 API 全表（锁定值，avatar-core-v3.2.7）

### 1.1 初始化
```java
AvatarPlatformConfig config = new AvatarPlatformConfig.Builder()
    .setAppId(appId)
    .setApikey(apiKey)        // ⚠️ 小写 k
    .setApiSecret(apiSecret)
    .setServerUrl("wss://avatar.cn-huadong-1.xf-yun.com/v1/interact")  // 必设，否则 600003
    .setLogLevel(LogLevel.INFO)
    .build();
AvatarPlatform.initialize(getApplicationContext(), config, (code, msg) -> {
    if ("0".equals(code)) { /* 成功, 主线程里 getController + 配参 + start */ }
    else { /* 失败 code/msg */ }
});
AvatarPlayController controller = AvatarPlatform.getController();
```

### 1.2 播放器 + 渲染（关键：黑屏根因）
```java
IStreamPlayer player = StreamPlayerFactory.createPlayer(this, AvatarConstant.STREAM_XRTC);
player.setRenderArea(mAvatarContainer);   // 传容器 ViewGroup, SDK 自管渲染面; 不要用 getRenderView 分支
controller.setStreamPlayer(player);        // 内部自动 bindAvatar + setAvatarListener
```

### 1.3 全局参数（stream 挂在 avatar 上）
```java
AvatarParams params = new AvatarParams();
AvatarParams.Stream stream = new AvatarParams.Stream();
stream.setProtocol(AvatarConstant.STREAM_XRTC);       // "xrtc"
// bitrate 为裸 int(kbps)，直接 2000，无 /1024 陷阱（那是 Web SDK 的坑）；fps/alpha 可选
AvatarParams.Avatar avatar = new AvatarParams.Avatar();
avatar.setAvatarId("118801001");                       // 已授权，必须显式传
avatar.setStream(stream);                              // ⚠️ stream 挂 avatar，不是顶层
AvatarParams.TTS tts = new AvatarParams.TTS();
tts.setVcn("x4_lingxiaoqi_oral");                      // 已授权
AvatarParams.Subtitle sub = new AvatarParams.Subtitle();
sub.setSubtitle(1); sub.setFontColor("#FFFFFF");
AvatarParams.Scene scene = new AvatarParams.Scene(); scene.setSceneId(sceneId);
params.setAvatar(avatar); params.setTTS(tts); params.setSubtitle(sub); params.setScene(scene);
controller.setGlobalParams(params);
controller.setListenerHandler(mUiHandler);            // 回调切主线程
controller.addAvatarListener(mAvatarListener);
controller.start();
```

### 1.4 事件监听（IAvatarListener 三方法）
```java
new IAvatarListener() {
  public void onResult(String type, byte[] data, String extra) {
    // type: "asr"/"nlp" (AvatarDataType.RESPONSE_*); 文本在 extra 的 JSON, 不在 data!
    // nlp: extra={"answer":{"text":"..."},"index":N,"status":1|2,"request_id":"...","service":"docqa|openai"}
    //   status=1 中间片, status=2 结束; 同 request_id 的分片按序累加成一句
    // asr: extra={"text":"..."}
  }
  public void onEvent(String type, String value) {
    // type: frame_start/frame_end/tts_duration/audit_result/... 状态事件
  }
  public void onError(String code, String desc, String extra) { }
}
```

### 1.5 四大交互
```java
// 1. 文本交互(走NLP+知识库): writeText + TextParams.setNlp(true)
TextParams tp = new TextParams(); tp.setNlp(true);
controller.writeText(question, tp);          // 答案在 onResult(type="nlp") 的 extra

// 2. 文本驱动播报(不走NLP): writeText 默认 nlp=false
controller.writeText(broadcastText);         // 直接朗读

// 3. 打断
controller.interrupt();

// 4. 语音交互: AudioRecorder + setAudioRecorder(内部自动泵PCM)
AudioRecorder recorder = new AudioRecorder(
    MediaRecorder.AudioSource.MIC, 16000, AudioFormat.ENCODING_PCM_16BIT, AudioFormat.CHANNEL_IN_MONO); // 必须16000
recorder.init();
AudioParams ap = new AudioParams(); ap.setNlp(true);
controller.setAudioRecorder(recorder, ap);   // 内部注册 PcmDataListener 自动 writeAudio
recorder.startRecord();  // 说话
recorder.stopRecord();   // 松手 → onResult(asr) → onResult(nlp)
```

### 1.6 生命周期
```java
// onDestroy: 先停录音再停控制器
if (recording) recorder.stopRecord();
controller.removeAvatarListener(listener);
controller.stop();
controller.destroy();
```

---

## 2. 六步构建流程（严格按序，每步带验证）

**Step 1 — 下载 SDK AAR**（调用 `avatar-artifact-download` skill，platform=android）
- OSS 直链：`https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/avatar-android-sdk.zip`（~79MB, v3.2.7）
- 解压后放入 `app/libs/`：`avatar-core-v3.2.7.aar` + `xrtcsdk-5.2024.3.0_00_hotfix1.aar`
- 验证：`ls app/libs/*.aar` 两个都在。

**Step 2 — 建工程骨架**（gradle-8.x + AGP 8.1.4，见 §3 版本矩阵）
- 用现成 gradle 生成 wrapper：`gradle wrapper --gradle-version 8.0.2 --distribution-type bin`
- 目录：settings.gradle / build.gradle / gradle.properties / app/build.gradle / app/src/main/{AndroidManifest.xml,java/...,res/layout,assets}
- 验证：`gradlew --version` 显示 Gradle 8.x / JVM 17。

**Step 3 — 权限 + build.gradle**（见 §3 模板）
- AndroidManifest 4 权限：INTERNET / ACCESS_NETWORK_STATE / RECORD_AUDIO / **BLUETOOTH_CONNECT**(API31+ XRTC必需)
- build.gradle：`sourceSets{ main{ jniLibs.srcDirs=['src/main/jniLibs','libs'] } }` + okhttp/gson/appcompat 依赖

**Step 4 — 凭据文件**（用 `tools/_fetch_creds.py <输出路径>` 拉 appId/apiKey/apiSecret，密钥不进对话）
- 合并 sceneId/avatarId/vcn/serverUrl 写入 `app/src/main/assets/credentials.json`
- 加入 `.gitignore`（HARD-GATE：apiSecret 不入 git；assets 明文进 APK 仅限 demo/内测，生产改服务端签名）

**Step 5 — MainActivity**（初始化+渲染+监听，按 §1.1-1.4，见 §4 完整模板）
- 从 assets 读 credentials → initialize → getController → setGlobalParams → setStreamPlayer → addAvatarListener → start

**Step 6 — 四功能 + 编译真机**（按 §1.5）
- `gradlew :app:assembleDebug`（**用 daemon，不加 --no-daemon**）
- `adb -s <设备> install -r app/build/outputs/apk/debug/app-debug.apk`
- 验证知识库命中：发健身问题 → logcat 看 `onResult type=nlp ... "service":"docqa" ... "sourceDetail":"xxx.md"`

---

## 3. 版本矩阵 + gradle 性能配置（编译不卡的关键）

### 3.1 版本矩阵（JDK 17 场景，本次验证组合）
| 项 | 值 |
|----|-----|
| JDK | 17 |
| AGP | **8.1.4** |
| Gradle | **8.0.2**（AGP 8.1 需 Gradle 8.0+） |
| compileSdk / targetSdk | 34 |
| minSdk | 26（SDK 支持下限之上） |
> JDK 11 场景才用 AGP 7.x/Gradle 7.x。**JDK17 配 Gradle7.x 会同步失败**。

### 3.2 `gradle.properties`（必须写入，解决 22 分钟→首次3-5分钟/增量秒级）
```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configureondemand=true
android.useAndroidX=true
```

### 3.3 编译规范（HARD-GATE）
- **永远用 `gradlew`（复用 daemon），严禁 `--no-daemon`**——本次 22 分钟慢就是关了 daemon + 首次下载。
- settings.gradle 的 `dependencyResolutionManagement.repositories` 加国内镜像加速首次依赖：
  ```gradle
  maven { url 'https://maven.aliyun.com/repository/google' }
  maven { url 'https://maven.aliyun.com/repository/public' }
  google(); mavenCentral()
  ```
- 首次编译会下载 AGP+AndroidX（约 3-5 分钟属正常），之后增量秒级。用 `run_in_background` 跑编译，别干等。

---

## 4. .so 原生库处理（避免重复冲突）

- **AAR 自带全套 xrtc .so**（libxrtc/libiRTCEngine/libjingle_peerconnection 等）——`jniLibs.srcDirs` 含 `'libs'` 即自动打包。
- **不要**再手动把解压包 `webrtc/*.so` 放进 `src/main/jniLibs`——会与 AAR 内同名 .so 重复，AGP 报
  `2 files found for path .../libjingle_peerconnection_so.so`。**只靠 AAR 提供即可**。
- 解压包 `rtmp/*.so`（ijkplayer）**仅当流协议选 rtmp 时**才需要 + 加依赖 `tv.danmaku.ijk.media:ijkplayer-exo:0.8.8`；本方案用 **xrtc**，跳过。
- abiFilters 可选优化（`arm64-v8a`,`armeabi-v7a`），遇 .so 冲突再加 `packagingOptions{ jniLibs{ useLegacyPackaging=true } }`。

---

## 5. 一次跑通验证清单

- [ ] 两个 AAR 在 app/libs/
- [ ] gradle.properties 六项性能配置就位
- [ ] `gradlew :app:assembleDebug` → BUILD SUCCESSFUL（无 duplicate .so 报错）
- [ ] `adb install -r` → Success
- [ ] 启动无崩溃，logcat `onEvent type=frame_start`（虚拟人开始播报）
- [ ] 虚拟人形象**渲染到屏幕**（截图确认，非黑屏——靠 setRenderArea）
- [ ] 发健身问题 → `onResult type=nlp` 的 extra 含 `"service":"docqa"` + `"sourceDetail":"xxx.md"`（命中知识库）
- [ ] 字幕区显示 nlp 流式文本（按 request_id 累加）
- [ ] 语音：按住说话 → `onResult type=asr` 有识别文本 → nlp 回答

> 完整可跑模板（MainActivity.java / build.gradle / settings.gradle / AndroidManifest.xml / activity_main.xml）见 §6。

---

## 6. 完整可跑模板（本次真机验证版，逐字可复用）

### 6.1 settings.gradle
```gradle
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven { url 'https://maven.aliyun.com/repository/google' }
        maven { url 'https://maven.aliyun.com/repository/public' }
        google(); mavenCentral()
        flatDir { dirs 'app/libs' }
    }
}
rootProject.name = "FitnessAvatar"
include ':app'
```

### 6.2 根 build.gradle
```gradle
plugins { id 'com.android.application' version '8.1.4' apply false }
```

### 6.3 app/build.gradle
```gradle
plugins { id 'com.android.application' }
android {
    namespace 'com.example.fitnessavatar'
    compileSdk 34
    defaultConfig {
        applicationId "com.example.fitnessavatar"
        minSdk 26
        targetSdk 34
        versionCode 1
        versionName "1.0"
        ndk { abiFilters 'arm64-v8a', 'armeabi-v7a' }
    }
    sourceSets { main { jniLibs.srcDirs = ['src/main/jniLibs', 'libs'] } }
    buildTypes { release { minifyEnabled false } }
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
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
}
```

### 6.4 AndroidManifest.xml（4 权限 + Activity）
```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>
    <application android:label="健身虚拟人"
        android:theme="@style/Theme.AppCompat.DayNight.NoActionBar"
        android:usesCleartextTraffic="true">
        <activity android:name=".MainActivity" android:exported="true"
            android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
```

### 6.5 credentials.json（assets/，加入 .gitignore）
```json
{
  "appId": "<YOUR_APP_ID>",
  "apiKey": "<平台apiKey>",
  "apiSecret": "<平台apiSecret>",
  "sceneId": "<接口场景ID>",
  "avatarId": "118801001",
  "vcn": "x4_lingxiaoqi_oral",
  "serverUrl": "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"
}
```

### 6.6 MainActivity.java
> 完整实现见配套文件 `android-mainactivity-template.java`（同目录）。关键点：assets 读凭据 → initialize(3参) →
> getController → setGlobalParams(stream挂avatar) → createPlayer("xrtc")+setRenderArea(容器) → setStreamPlayer →
> addAvatarListener(IAvatarListener) → start；交互 writeText(text,TextParams.setNlp(true))，播报 writeText(text)；
> nlp 结果解析 extra 的 answer.text 并按 request_id 流式累加；语音 AudioRecorder(16000)+setAudioRecorder。

### 6.7 gradle.properties / local.properties
```properties
# gradle.properties — 见 §3.2 六项
# local.properties — sdk.dir=C\:\\Android\\Sdk （指向本机 Android SDK）
```



