# iOS SDK 集成指南

**适用场景**: 原生 iOS 应用集成讯飞虚拟人 SDK

---

## 一、SDK 文件

### 必需文件
```
Frameworks/
├── AvatarSDK.framework          # 核心 SDK
└── XRTCSDK.framework            # XRTC 视频流 SDK
```

### 自动下载
使用 `avatar-artifact-download` skill 自动下载：
```
platform: ios
target_dir: Frameworks/
```

### 验证
```bash
ls Frameworks/*.framework
# 应该看到两个 framework
```

---

## 二、核心 API

### 2.1 初始化平台

```objc
// ViewController.m

// Step 1: 构建配置
AvatarPlatformConfig *config = [AvatarPlatformConfig new];
config.appId = APP_ID;
config.apiKey = API_KEY;
config.apiSecret = API_SECRET;
config.serverUrl = @"wss://avatar.cn-huadong-1.xf-yun.com/v1/interact";
config.logLevel = AvatarLogLevelVerbose;
config.uid = @"user_unique_id";

// Step 2: 初始化 SDK
NSError *error = nil;
[AvatarPlatform initializeWithConfig:config error:&error];
if (error) {
    NSLog(@"初始化失败: %@", error.localizedDescription);
    return;
}

// Step 3: 获取控制器
AvatarPlayController *controller = [AvatarPlatform sharedController];
```

### 2.2 创建视频播放器

```objc
// Step 1: 准备容器 UIView
UIView *videoContainer = self.videoContainerView;

// Step 2: 创建播放器
StreamPlayer *streamPlayer = [StreamPlayerFactory createStreamPlayerWithView:videoContainer];

// Step 3: 设置到控制器
[controller setStreamPlayer:streamPlayer];
```

### 2.3 设置全局参数

```objc
AvatarParams *params = [AvatarParams new];

// 视频流配置
AvatarStreamParams *stream = [AvatarStreamParams new];
stream.protocol = @"xrtc";
stream.fps = 25;
stream.bitrate = 2000;
stream.alpha = 0;  // 0=普通背景, 1=透明背景

// 形象配置（固定模板）
AvatarAvatarParams *avatar = [AvatarAvatarParams new];
avatar.avatarId = @"118801001";  // 固定使用标准形象
avatar.width = 720;
avatar.height = 1280;
avatar.stream = stream;

// 发音人配置（固定模板）
AvatarTTSParams *tts = [AvatarTTSParams new];
tts.vcn = @"x4_yezi";  // 固定使用叶子女声
tts.speed = 50;
tts.pitch = 50;
tts.volume = 50;

// 场景配置
AvatarSceneParams *scene = [AvatarSceneParams new];
scene.sceneId = SCENE_ID;

// 调度配置
AvatarDispatchParams *dispatch = [AvatarDispatchParams new];
dispatch.interactiveMode = 0;  // 0=追加模式, 1=打断模式

params.avatar = avatar;
params.tts = tts;
params.scene = scene;
params.dispatch = dispatch;

[controller setGlobalParams:params];
```

### 2.4 注册事件监听

```objc
[controller addAvatarListener:^(AvatarEvent event, NSDictionary *data) {
    switch (event) {
        case AvatarEventReady:
            // 虚拟人就绪
            NSLog(@"虚拟人已就绪");
            break;
            
        case AvatarEventError: {
            NSInteger code = [data[@"code"] integerValue];
            NSString *message = data[@"message"];
            NSLog(@"Error %ld: %@", (long)code, message);
            break;
        }
            
        case AvatarEventNlpResult: {
            NSString *text = data[@"text"];
            NSLog(@"NLP回复: %@", text);
            break;
        }
            
        case AvatarEventFrameStop: {
            NSInteger vmrStatus = [data[@"vmr_status"] integerValue];
            if (vmrStatus == 2) {
                // 播报完成
                NSLog(@"播报完成");
            }
            break;
        }
            
        case AvatarEventAsrResult: {
            NSString *text = data[@"text"];
            NSLog(@"ASR: %@", text);
            break;
        }
            
        default:
            break;
    }
}];
```

### 2.5 启动虚拟人

```objc
[controller start];
```

### 2.6 文本交互

```objc
// 发送文本消息
[controller sendText:@"你好，请介绍一下力量训练"];
```

### 2.7 停止和释放

```objc
- (void)dealloc {
    [controller stop];
    [controller release];
    [streamPlayer release];
}
```

---

## 三、权限配置

### 3.1 Info.plist

```xml
<!-- 麦克风权限（语音交互必需） -->
<key>NSMicrophoneUsageDescription</key>
<string>需要使用麦克风进行语音对话</string>

<!-- 相机权限（可选） -->
<key>NSCameraUsageDescription</key>
<string>需要使用相机</string>

<!-- 网络权限 -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
</dict>
```

### 3.2 AVAudioSession 配置

```objc
// 配置音频会话
AVAudioSession *session = [AVAudioSession sharedInstance];
NSError *error = nil;

[session setCategory:AVAudioSessionCategoryPlayAndRecord
         withOptions:AVAudioSessionCategoryOptionDefaultToSpeaker
               error:&error];

if (error) {
    NSLog(@"Audio session error: %@", error);
}

[session setActive:YES error:&error];
```

---

## 四、Xcode 配置

### 4.1 添加 Framework

1. 将 `AvatarSDK.framework` 和 `XRTCSDK.framework` 拖入项目
2. Target → General → Frameworks, Libraries, and Embedded Content
3. 设置为 "Embed & Sign"

### 4.2 Build Settings

```
Other Linker Flags: -ObjC
Enable Bitcode: No
```

---

## 五、常见错误处理

### 5.1 错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 10110 | appId 不存在 | 检查 appId 配置 |
| 10113 | apiSecret 错误 | 检查签名生成 |
| 10114 | sceneId 不存在 | 检查场景配置 |
| 10120 | avatarId 未授权 | 使用已授权的形象 |
| 20002 | 视频播放失败 | 检查播放器配置 |

### 5.2 常见问题

**Q: 黑屏无视频？**
- 检查 `StreamPlayer` 是否正确创建
- 检查容器 UIView 是否添加到视图层级
- 查看日志是否有错误码

**Q: 无法启动？**
- 检查网络连接
- 检查 API 凭据是否正确
- 查看控制台日志

---

## 六、完整示例

完整的 ViewController 示例见本指南第二节各步骤的代码。

关键要点：
1. ✅ 使用 `[AvatarPlatform initializeWithConfig:error:]` 初始化
2. ✅ 使用 `[StreamPlayerFactory createStreamPlayerWithView:]` 创建播放器
3. ✅ 使用 `AvatarPlayController` 管理虚拟人
4. ✅ 固定使用 `avatarId = @"118801001"` 和 `vcn = @"x4_yezi"`
5. ✅ 注册事件监听器处理回调

**切勿**手写 WebSocket 协议代码，必须使用 SDK 提供的 API。

---

## 七、Swift 支持

iOS SDK 同样支持 Swift：

```swift
// 初始化
let config = AvatarPlatformConfig()
config.appId = APP_ID
config.apiKey = API_KEY
config.apiSecret = API_SECRET
config.serverUrl = "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"

do {
    try AvatarPlatform.initialize(with: config)
} catch {
    print("初始化失败: \(error)")
}

// 获取控制器
let controller = AvatarPlatform.shared()

// 创建播放器
let player = StreamPlayerFactory.createStreamPlayer(with: videoView)
controller.streamPlayer = player

// 设置参数（使用固定模板）
let params = AvatarParams()
params.avatar.avatarId = "118801001"
params.tts.vcn = "x4_yezi"
params.scene.sceneId = SCENE_ID
controller.setGlobalParams(params)

// 启动
controller.start()

// 发送文本
controller.sendText("你好")
```

---

## 八、参考资料

- 官方文档：https://www.xfyun.cn/doc/avatar/iOS_SDK_summary.html
- SDK 下载：使用 `avatar-artifact-download` skill
- 配置模板：本指南第 2.3 节
