# Step 5: 生成修复方案

## 5.1 修复方案结构

```markdown
# 故障诊断报告

## 问题概要
- 症状: 黑屏
- 平台: Android
- 错误码: 20002
- 根因: 播放器创建失败 - XRTC SDK 未引入

## 根因分析
错误码 20002 表示播放器创建失败。在 Android 平台使用 XRTC 协议时，
需要引入 xrtcsdk-*.aar 依赖。检查发现 app/libs/ 目录下缺少该文件。

## 修复步骤

### Step 1: 下载 XRTC SDK
从虚拟人平台下载 Android SDK 包，解压后找到:
- xrtcsdk-5.2024.3.0_00_hotfix1.aar

### Step 2: 复制到项目
cp xrtcsdk-5.2024.3.0_00_hotfix1.aar app/libs/

### Step 3: 确认 Gradle 配置
检查 app/build.gradle 是否包含:
```gradle
dependencies {
    implementation fileTree(include: ['*.jar', '*.aar'], dir: 'libs')
}
```

### Step 4: 同步并重新编译
./gradlew clean
./gradlew assembleDebug

### Step 5: 重新安装测试
adb install -r app/build/outputs/apk/debug/app-debug.apk

## 验证方法
1. 启动应用
2. 触发虚拟人播放
3. 检查日志: 应无 20002 错误
4. 确认虚拟人视频正常显示

## 预防措施
1. 在 preflight 阶段检查 XRTC SDK 是否存在
2. 添加播放器创建失败的错误提示
3. 文档中明确 XRTC 协议依赖要求

## 相关文档
- Android SDK 集成指南: https://doc.xfyun.cn/avatar/android-sdk
- 错误码说明: https://doc.xfyun.cn/avatar/error-codes
```

## 5.2 修复优先级

**Critical (立即修复)**:
- 凭据错误 (10110/10113/10114)
- 资源未授权 (10120/10121)
- SDK 初始化失败 (20001)

**High (优先修复)**:
- 播放器创建失败 (20002)
- 录音器启动失败 (20003)
- 网络连接超时 (10200)

**Medium (可延后)**:
- 参数配置优化
- 性能调优
- 用户体验改进
