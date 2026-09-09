# 计划文档结构模板

对应 Step 2.2：plan-writer 生成的实现计划文档结构。以下为完整模板（原样保留）。

````markdown
# 虚拟人集成实现计划

## 概览

- 项目: xxx
- 平台: Web
- 实施类型: 首次接入
- 预计步骤: 8 步
- 预计时间: 2-4 小时

---

## 步骤清单

### Step 1: SDK 安装与引入

**目标**: 将虚拟人 SDK 集成到项目中

**前置条件**:
- [x] 环境门禁已通过
- [x] SDK 文件已下载

**操作**:

#### Web
```bash
# 1. 将 SDK 放到项目目录
cp -r ~/Downloads/avatar-sdk-web_3.2.3.1002 ./src/sdk/

# 2. 在主文件中引入
# src/avatar-integration.js
import AvatarPlatform, { 
  PlayerEvents, 
  SDKEvents 
} from './sdk/avatar-sdk-web_3.2.3.1002/index.js';
```

#### Android
```gradle
// 1. 复制 AAR 到 app/libs/
// avatar-core-v3.2.7.aar
// xrtcsdk-5.2024.3.0_00_hotfix1.aar

// 2. 确认 app/build.gradle 配置
dependencies {
    implementation fileTree(include: ['*.jar', '*.aar'], dir: 'libs')
    implementation 'com.squareup.okhttp3:okhttp:3.11.0'
}
```

#### iOS
```
1. 拖拽 Framework 到 Xcode 工程
   - AvatarSDK.framework
   - XRTCSDK.framework

2. 设置 Embed & Sign
   Target → General → Frameworks → Embed & Sign

3. 添加系统库依赖
   - libc++.tbd
```

**验证**:
- [ ] 编译无报错
- [ ] 模块导入成功
- [ ] (iOS) Framework 签名正确

**风险**:
- Web: ESM 模块路径错误
- Android: Gradle 同步失败
- iOS: 签名配置错误

**回滚**: 删除 SDK 文件，恢复原配置

---

### Step 2: 环境配置

**目标**: 配置权限、依赖和构建参数

**操作**:

#### Web
```javascript
// 1. 确认在 HTTPS 或 localhost 环境
// 检查 vite.config.js / webpack.config.js

// 2. 配置环境变量（可选）
// .env
VITE_AVATAR_APP_ID=your_app_id
VITE_AVATAR_SCENE_ID=your_scene_id
// 注意: apiSecret 不要提交到代码仓库
```

#### Android
```xml
<!-- AndroidManifest.xml -->
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
<uses-permission android:name="android.permission.RECORD_AUDIO"/>

<!-- 运行时权限申请 -->
```

```gradle
// app/build.gradle
android {
    defaultConfig {
        minSdkVersion 21
    }
    sourceSets {
        main {
            jniLibs.srcDirs = ['libs']
        }
    }
}
```

#### iOS
```xml
<!-- Info.plist -->
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>
```

```
Xcode Build Settings:
- Enable Bitcode: NO
- Bundle ID: 配置
- Team: 选择开发者账号
```

**验证**:
- [ ] 权限配置完整
- [ ] 编译配置正确
- [ ] (Android/iOS) 运行时权限申请流程已实现

**风险**:
- 权限配置遗漏导致运行时报错

---

### Step 3: SDK 初始化

**目标**: 完成 SDK 初始化，建立服务连接能力

**操作**:

#### Web
```javascript
// src/avatar-integration.js

// 1. 创建 AvatarPlatform 实例
const avatar = new AvatarPlatform();

// 2. 设置接口信息
avatar.setApiInfo({
  serverUrl: 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
  appId: 'your_app_id',
  apiKey: 'your_api_key',
  apiSecret: 'your_api_secret',
  sceneId: 'your_scene_id'
});

// 3. 注册事件监听
avatar
  .on(SDKEvents.connected, () => {
    console.log('虚拟人连接成功');
  })
  .on(SDKEvents.error, (e) => {
    console.error('错误:', e?.code, e?.message);
  })
  .on(SDKEvents.disconnected, (e) => {
    if (e) console.error('异常断开:', e);
  });
```

#### Android
```java
// MainActivity.java

// 1. 初始化配置
AvatarPlatformConfig config = new AvatarPlatformConfig.Builder()
    .setAppId(appId)
    .setApikey(apiKey)
    .setApiSecret(apiSecret)
    .setServerUrl("wss://avatar.cn-huadong-1.xf-yun.com/v1/interact")
    .setLogLevel(LogLevel.VERBOSE)
    .setUid("user_unique_id")
    .build();

// 2. 初始化 SDK
AvatarError error = AvatarPlatform.initialize(context, config);
if (error != null && !error.isSuccess()) {
    Log.e(TAG, "初始化失败: " + error.getDesc());
    return;
}

// 3. 获取控制器
AvatarPlayController controller = AvatarPlatform.getController();
controller.addAvatarListener(avatarListener);
```

#### iOS
```objc
// ViewController.m

// 1. 初始化配置
AvatarPlatformConfig *config = [AvatarPlatformConfig new];
config.appId(appId)
      .apiKey(apiKey)
      .apiSecret(apiSecret)
      .serverUrl(@"wss://avatar.cn-huadong-1.xf-yun.com/v1/interact")
      .uid(@"user_unique_id");

// 2. 初始化 SDK
AvatarError *error = [AvatarPlatform initializeConfig:config];
if (error && ![error isSuccess]) {
    NSLog(@"初始化失败: %d %@", error.code, error.desc);
    return;
}

// 3. 获取控制器
AvatarPlayController *controller = [AvatarPlatform controller];
controller.delegate = self;
```

**验证**:
- [ ] SDK 初始化返回成功
- [ ] 事件监听器注册成功
- [ ] 控制器获取成功

**注意事项**:
- apiSecret 不要硬编码，从环境变量或配置文件读取
- 生产环境建议服务端签名，客户端不持有 apiSecret

---

### Step 4: 播放器创建与配置

**目标**: 创建视频播放器，配置渲染参数

**操作**:

#### Web
```javascript
// 1. 创建播放器（默认已创建，也可手动）
const player = avatar.player || avatar.createPlayer();

// 2. 配置播放器参数
// 透明背景需要同时配置
player.alpha = true;  // 如果需要透明背景

// 3. 处理自动播放限制
player.on(PlayerEvents.playNotAllowed, () => {
  console.log('浏览器阻止自动播放，需要用户交互');
  // 显示提示，引导用户点击
  document.addEventListener('click', () => {
    player.resume();
  }, { once: true });
});
```

#### Android
```java
// 1. 创建播放器
IStreamPlayer streamPlayer = StreamPlayerFactory.createPlayer(context, "xrtc");

// 2. 配置播放器参数
StreamPlayerParams playerParams = new StreamPlayerParams();
playerParams.setBgAlpha(true);  // 透明背景
playerParams.setAlphaRenderMode(AlphaRenderMode.V2);
playerParams.setVolume(1.0);
streamPlayer.setPlayerParams(playerParams);

// 3. 设置渲染容器
streamPlayer.setRenderArea(flAvatarContainer);

// 4. 设置播放器监听
streamPlayer.setPlayerListener(playerListener);
```

#### iOS
```objc
// 1. 创建播放器
IStreamPlayer *player = [[IStreamPlayer alloc] initPlayerProtocal:@"xrtc"];

// 2. 配置播放器参数
StreamPlayerParams *playerParams = [StreamPlayerParams new];
playerParams.volume(1.0).alpha(YES);  // 透明背景
player.playerParams = playerParams;

// 3. 设置渲染视图
player.renderView = self.remoteView;
```

**验证**:
- [ ] 播放器创建成功
- [ ] 渲染容器已设置且有有效尺寸
- [ ] 播放器参数配置正确

---

### Step 5: 全局参数配置

**目标**: 配置虚拟人形象、声音、视频流参数

**操作**:

#### Web
```javascript
avatar.setGlobalParams({
  // 视频流参数（顶层）
  stream: { 
    protocol: 'xrtc',
    fps: 25,
    bitrate: 2000,
    alpha: 1  // 透明背景
  },
  
  // 形象参数
  avatar: { 
    avatar_id: 'your_avatar_id',
    width: 720,
    height: 1280,
    // 关键：avatar.stream 必须完整配置（protocols.md 要求）
    stream: {
      protocol: 'xrtc',
      fps: 25,
      bitrate: 2000,
      alpha: 1
    }
  },
  
  // 发音人参数
  tts: { 
    vcn: 'your_vcn',
    speed: 50,
    pitch: 50,
    volume: 50
  }
});
```

#### Android
```java
AvatarParams params = new AvatarParams();

// 视频流
AvatarParams.Stream stream = new AvatarParams.Stream();
stream.setProtocol("xrtc");
stream.setFps(25);
stream.setBitrate(2000);
stream.setAlpha(1);  // 透明背景

// 形象
AvatarParams.Avatar avatar = new AvatarParams.Avatar();
avatar.setAvatarId(avatarId);
avatar.setWidth(720);
avatar.setHeight(1280);
avatar.setStream(stream);

// 发音人
AvatarParams.TTS tts = new AvatarParams.TTS();
tts.setVcn(vcn);
tts.setSpeed(50);

// 场景
AvatarParams.Scene scene = new AvatarParams.Scene();
scene.setSceneId(sceneId);

// 调度参数
AvatarParams.Dispatch dispatch = new AvatarParams.Dispatch();
dispatch.setInteractiveMode(0);  // 0追加/1打断

params.setAvatar(avatar);
params.setTTS(tts);
params.setScene(scene);
params.setDispatch(dispatch);

controller.setGlobalParams(params);
controller.setStreamPlayer(streamPlayer);
```

#### iOS
```objc
AvatarParams *params = [AvatarParams new];

// 视频流
AvatarParamsStream *stream = [AvatarParamsStream new];
stream.protocol(@"xrtc").fps(25).bitrate(2000).alpha(YES);

// 形象
AvatarParamsAvatar *avatar = [AvatarParamsAvatar new];
avatar.avatarId(avatarId)
      .width(720)
      .height(1280)
      .stream(stream);

// 发音人
AvatarParamsTTS *tts = [AvatarParamsTTS new];
tts.vcn(vcn).speed(50).pitch(50).volume(50);

// 场景
AvatarParamsScene *scene = [AvatarParamsScene new];
scene.sceneId(sceneId);

// 调度
AvatarParamsDispatch *dispatch = [AvatarParamsDispatch new];
dispatch.interactiveMode(0);

params.avatar(avatar).tts(tts).scene(scene).dispatch(dispatch);

controller.globalParams = params;
controller.streamPlayer = player;
```

**验证**:
- [ ] 参数配置完整
- [ ] avatarId 和 vcn 已授权
- [ ] 视频宽高为 4 的倍数

---

### Step 6: 启动虚拟人

**目标**: 建立 WebSocket 连接，获取视频流并开始播放

**操作**:

#### Web
```javascript
// 启动虚拟人（需要在渲染容器准备好后）
try {
  await avatar.start({ 
    wrapper: document.querySelector('.avatar-container') 
  });
  console.log('虚拟人启动成功');
} catch (err) {
  console.error('启动失败:', err);
}
```

#### Android
```java
// 启动虚拟人
controller.start();
```

#### iOS
```objc
// 启动虚拟人
[controller start];
```

**验证**:
- [ ] 收到 `connected` 事件
- [ ] 收到 `stream_start` 事件
- [ ] 播放器开始渲染视频
- [ ] 看到虚拟人画面

**常见问题**:
- 黑屏: 检查播放器配置、avatarId 授权
- 连接失败: 检查凭据、网络
- 无声音: (Web) 处理自动播放限制

---

### Step 7: 实现核心功能

**目标**: 实现文本驱动、语音交互等核心功能

#### 7.1 文本驱动

```javascript
// Web
await avatar.writeText('你好，欢迎使用虚拟人服务', { nlp: false });

// Android
controller.writeText("你好，欢迎使用虚拟人服务", null);

// iOS
[controller writeText:@"你好，欢迎使用虚拟人服务" textParams:nil];
```

#### 7.2 文本交互（NLP）

```javascript
// Web
await avatar.writeText('请介绍一下你自己', { nlp: true });

// Android
TextParams textParams = new TextParams();
textParams.setNlp(true);
controller.writeText("请介绍一下你自己", textParams);

// iOS
TextParams *textParams = [TextParams new];
textParams.nlp = YES;
[controller writeText:@"请介绍一下你自己" textParams:textParams];
```

#### 7.3 语音交互

```javascript
// Web
const recorder = avatar.recorder || avatar.createRecorder({ sampleRate: 16000 });

// 短语音录音（按住说话）
recorder.startRecord(60 * 1000, () => {
  console.log('录音结束');
}, { nlp: true });

// 停止录音
recorder.stopRecord();

// Android
AudioRecorder recorder = new AudioRecorder(
    MediaRecorder.AudioSource.MIC,
    16000,
    AudioFormat.ENCODING_PCM_16BIT,
    AudioFormat.CHANNEL_IN_MONO
);
recorder.init();
recorder.startRecord();
// ...
recorder.stopRecord();

// iOS
AudioRecorder *recorder = [[AudioRecorder alloc] initWithDelegate:self];
[recorder startRecord];
// ...
[recorder stopRecord];
```

**验证**:
- [ ] 文本驱动：虚拟人播报文本
- [ ] 文本交互：收到 NLP 回复并播报
- [ ] 语音交互：录音上传、ASR 识别、NLP 回复

---

### Step 8: 错误处理与资源释放

**目标**: 完善错误处理，正确释放资源

**操作**:

#### 错误处理

```javascript
// Web
avatar.on(SDKEvents.error, (e) => {
  console.error('错误码:', e?.code, '描述:', e?.message);
  
  switch(e?.code) {
    case '10110':
      alert('appId 错误，请检查配置');
      break;
    case '10113':
      alert('apiSecret 错误，请检查签名');
      break;
    case '10120':
      alert('avatarId 未授权');
      break;
    // ... 其他错误码
  }
});

// Android
@Override
public void onError(String errorCode, String errorDesc, String extra) {
    Log.e(TAG, "错误: " + errorCode + " " + errorDesc);
    
    switch(errorCode) {
        case "10110":
            showToast("appId 错误");
            break;
        // ...
    }
}

// iOS
- (void)avatarOnError:(AvatarError *)error extra:(NSString *)extra {
    NSLog(@"错误: %d %@", error.code, error.desc);
    
    switch(error.code) {
        case 10110:
            [self showAlert:@"appId 错误"];
            break;
        // ...
    }
}
```

#### 资源释放

```javascript
// Web - 页面卸载时
avatar.stop();      // 停止虚拟人
avatar.destroy();   // 销毁实例

// Android - Activity onDestroy
if (recorder != null && recorder.isRecording()) {
    recorder.stopRecord();
}
controller.stop();
controller.destroy();

// iOS - ViewController dealloc
if (self.recorder.isRecording) {
    [self.recorder stopRecord];
}
[self.controller stop];
[self.controller destory];  // 注意: SDK 方法名为 destory
```

**验证**:
- [ ] 错误能正确捕获和提示
- [ ] 资源能正确释放
- [ ] 无内存泄漏

---

## 验证清单

### 功能验证
- [ ] SDK 初始化成功
- [ ] 虚拟人连接成功
- [ ] 视频播放正常
- [ ] 文本驱动工作正常
- [ ] 文本交互工作正常（如需）
- [ ] 语音交互工作正常（如需）
- [ ] 透明背景工作正常（如需）

### 异常验证
- [ ] 网络断开后重连
- [ ] 凭据错误时提示明确
- [ ] 权限拒绝时有引导
- [ ] 资源正确释放

### 性能验证
- [ ] 首帧延迟 < 3s
- [ ] 播放流畅无卡顿
- [ ] 内存占用合理

---

## 风险点

### 高风险
1. **凭据配置错误** → 连接失败
   - 缓解: 使用 preflight 验证
   
2. **权限未申请** → 录音失败
   - 缓解: 运行时权限检查

3. **协议配置错误** → 播放失败
   - 缓解: 按设计文档配置

### 中风险
1. **浏览器自动播放限制** (Web)
   - 缓解: 引导用户交互后播放

2. **弱网环境首帧慢**
   - 缓解: 显示 loading，降低码率

3. **低端设备解码能力不足**
   - 缓解: 降低分辨率和帧率

---

## 回滚策略

### 部分失败
- SDK 初始化失败 → 检查凭据，修复后重试
- 播放器创建失败 → 检查依赖，重新编译

### 完全失败
- 保留设计文档
- 删除已添加的代码
- 恢复原项目状态
- 重新执行 preflight 检查

---

## 下一步

实现计划已完成，准备进入 **avatar-executing** 阶段：
- 按步骤执行实现
- 每步完成后验证
- 遇到问题时参考错误码文档
````






