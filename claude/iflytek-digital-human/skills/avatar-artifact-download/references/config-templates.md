# SDK 下载配置

## 当前 OSS 下载配置

```yaml
SDK_URLS:
  web:
    version: "3.2.3.1002"
    filename: "avatar-web-sdk.zip"
    url: "https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/avatar-web-sdk.zip"
    size: "~5MB"
    verify_file: "index.js"
    
  android:
    version: "3.2.7"
    filename: "avatar-android-sdk.zip"
    url: "https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/avatar-android-sdk.zip"
    size: "~15MB"
    verify_files: ["avatar-core-*.aar", "xrtcsdk-*.aar"]
    
  ios:
    version: "3.2.1"
    filename: "avatar-ios-sdk.zip"
    url: "https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/avatar-ios-sdk.zip"
    size: "~20MB"
    verify_file: "AvatarSDK.framework"
```

链接是否可用以 `sdk_artifact.py ensure` 的实际请求、ZIP 校验和 SDK 入口校验为准；不得仅凭本文档声称长期有效。

---

## 下载失败

返回 `blocked_missing_sdk` 并保留同一 workflow。没有经过现场验证的替代源时，不生成官网链接或手动下载说明；修复网络、权限或配置后重跑确定性校验。

---

## 目标路径规范

### Web SDK
```
项目根目录/
└── sdk/
    └── （解压后的 SDK 文件）
        ├── index.js
        ├── index.d.ts
        └── ...
```

### Android SDK
```
项目根目录/
└── app/
    └── libs/
        ├── avatar-core-v3.2.7.aar
        └── xrtcsdk-5.2024.3.0.aar
```

### iOS SDK
```
项目根目录/
└── Frameworks/
    ├── AvatarSDK.framework/
    └── XRTCSDK.framework/
```

---

## 验证文件规则

下载完成后，验证以下关键文件是否存在：

**Web**: 
- `**/index.js` 存在

**Android**:
- `**/avatar-core-*.aar` 存在
- `**/xrtcsdk-*.aar` 存在

**iOS**:
- `**/AvatarSDK.framework` 存在

验证失败视为 SDK 缺失或不完整，不得进入完成上报。
