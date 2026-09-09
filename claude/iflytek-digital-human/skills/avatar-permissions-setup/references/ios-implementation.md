# iOS 平台权限实现

## Info.plist 配置

```xml
<!-- Info.plist -->

<!-- 麦克风权限说明（必需） -->
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>

<!-- 摄像头权限说明（可选） -->
<key>NSCameraUsageDescription</key>
<string>用于视频通话</string>

<!-- 照片库权限（可选） -->
<key>NSPhotoLibraryUsageDescription</key>
<string>用于保存虚拟人截图</string>
```

## 运行时权限申请

```objc
// ViewController.m

#import <AVFoundation/AVFoundation.h>

@implementation ViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    
    // 检查并申请麦克风权限
    [self checkAndRequestMicrophonePermission];
}

- (void)checkAndRequestMicrophonePermission {
    // 1. 检查当前权限状态
    AVAuthorizationStatus status = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio];
    
    switch (status) {
        case AVAuthorizationStatusAuthorized:
            // 已授权
            [self startVoiceInteraction];
            break;
            
        case AVAuthorizationStatusNotDetermined:
            // 未决定，申请权限
            [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio 
                                      completionHandler:^(BOOL granted) {
                dispatch_async(dispatch_get_main_queue(), ^{
                    if (granted) {
                        [self startVoiceInteraction];
                    } else {
                        [self showPermissionDeniedAlert];
                    }
                });
            }];
            break;
            
        case AVAuthorizationStatusDenied:
        case AVAuthorizationStatusRestricted:
            // 已拒绝或受限，引导到设置
            [self showSettingsAlert];
            break;
    }
}

- (void)showPermissionDeniedAlert {
    UIAlertController *alert = [UIAlertController 
        alertControllerWithTitle:@"需要麦克风权限"
        message:@"虚拟人语音交互功能需要使用麦克风"
        preferredStyle:UIAlertControllerStyleAlert];
    
    [alert addAction:[UIAlertAction actionWithTitle:@"确定" 
                                             style:UIAlertActionStyleDefault 
                                           handler:nil]];
    
    [self presentViewController:alert animated:YES completion:nil];
}

- (void)showSettingsAlert {
    UIAlertController *alert = [UIAlertController 
        alertControllerWithTitle:@"需要麦克风权限"
        message:@"请在设置中开启麦克风权限"
        preferredStyle:UIAlertControllerStyleAlert];
    
    [alert addAction:[UIAlertAction actionWithTitle:@"去设置" 
                                             style:UIAlertActionStyleDefault 
                                           handler:^(UIAlertAction *action) {
        NSURL *url = [NSURL URLWithString:UIApplicationOpenSettingsURLString];
        [[UIApplication sharedApplication] openURL:url options:@{} completionHandler:nil];
    }]];
    
    [alert addAction:[UIAlertAction actionWithTitle:@"取消" 
                                             style:UIAlertActionStyleCancel 
                                           handler:nil]];
    
    [self presentViewController:alert animated:YES completion:nil];
}

- (void)startVoiceInteraction {
    // 启动语音交互
    NSLog(@"权限已授予，开始语音交互");
    
    // 配置 AVAudioSession
    [self configureAudioSession];
}

- (void)configureAudioSession {
    AVAudioSession *session = [AVAudioSession sharedInstance];
    NSError *error = nil;
    
    // 设置 category（播放和录音）
    [session setCategory:AVAudioSessionCategoryPlayAndRecord 
                    mode:AVAudioSessionModeDefault 
                 options:AVAudioSessionCategoryOptionDefaultToSpeaker
                   error:&error];
    
    if (error) {
        NSLog(@"设置 AVAudioSession 失败: %@", error);
    }
    
    // 激活 session
    [session setActive:YES error:&error];
    
    if (error) {
        NSLog(@"激活 AVAudioSession 失败: %@", error);
    }
}

@end
```

## 监听权限变化（iOS）

```objc
// 监听音频中断通知
[[NSNotificationCenter defaultCenter] 
    addObserver:self
    selector:@selector(handleInterruption:)
    name:AVAudioSessionInterruptionNotification
    object:nil];

- (void)handleInterruption:(NSNotification *)notification {
    AVAudioSessionInterruptionType type = 
        [notification.userInfo[AVAudioSessionInterruptionTypeKey] unsignedIntegerValue];
    
    if (type == AVAudioSessionInterruptionTypeBegan) {
        // 中断开始（来电、权限撤销等）
        [self.recorder stopRecord];
    } else if (type == AVAudioSessionInterruptionTypeEnded) {
        // 中断结束
        AVAudioSessionInterruptionOptions options = 
            [notification.userInfo[AVAudioSessionInterruptionOptionKey] unsignedIntegerValue];
        
        if (options & AVAudioSessionInterruptionOptionShouldResume) {
            // 可以恢复
            [[AVAudioSession sharedInstance] setActive:YES error:nil];
        }
    }
}
```

## 问题诊断: iOS 录音无反应

**原因**:
- Info.plist 未配置 NSMicrophoneUsageDescription
- AVAudioSession 未激活
- 权限被拒绝

**解决**:
```xml
<!-- 1. Info.plist 配置 -->
<key>NSMicrophoneUsageDescription</key>
<string>用于虚拟人语音交互</string>
```

```objc
// 2. 激活 AVAudioSession
AVAudioSession *session = [AVAudioSession sharedInstance];
[session setCategory:AVAudioSessionCategoryPlayAndRecord error:nil];
[session setActive:YES error:nil];
```

**验证**:
```objc
// 检查权限状态
AVAuthorizationStatus status = 
    [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio];
NSLog(@"麦克风权限状态: %ld", (long)status);
// 0=NotDetermined, 1=Restricted, 2=Denied, 3=Authorized
```

## 问题诊断: 用户"不再询问"后无法申请权限（iOS）

```objc
if (status == AVAuthorizationStatusDenied) {
    // 引导到设置
    [[UIApplication sharedApplication] 
        openURL:[NSURL URLWithString:UIApplicationOpenSettingsURLString]
        options:@{} 
        completionHandler:nil];
}
```
