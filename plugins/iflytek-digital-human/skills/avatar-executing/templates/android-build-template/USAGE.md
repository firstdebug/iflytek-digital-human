# Android 构建模板使用指南（avatar-code-writer 专用）

当 avatar-code-writer 接到生成 Android 虚拟人工程的任务时，按以下步骤使用此模板：

## Step 1: 复制模板到目标目录

```bash
cp -r <plugin-root>/skills/avatar-executing/templates/android-build-template/* <目标工程根目录>/
```

## Step 2: 处理模板占位符

**settings.gradle.template** → settings.gradle:
```gradle
# 替换 {{PROJECT_NAME}} 为实际项目名（如 FitnessAvatarChat）
rootProject.name = "FitnessAvatarChat"  # 替换这行
```

**app-build.gradle.template** → app/build.gradle:
```gradle
# 替换 {{PACKAGE_NAME}} 为实际包名（如 com.fitness.avatar）
namespace 'com.fitness.avatar'          # 替换这行
applicationId "com.fitness.avatar"      # 替换这行
```

**build.gradle.template** → build.gradle:
```gradle
# 无需替换，直接重命名即可
```

## Step 3: 创建 app 目录结构

```bash
mkdir -p app/src/main/java/<包名路径>
mkdir -p app/src/main/res/layout
mkdir -p app/src/main/res/values
mkdir -p app/src/main/assets
mkdir -p app/libs
```

## Step 4: 放置 AAR 文件

将虚拟人 SDK 的两个 AAR 文件复制到 `app/libs/`:
- avatar-core-v3.2.7.aar
- xrtcsdk-5.2024.3.0_00_hotfix1.aar

## Step 5: 生成代码文件

**必须严格按 android-sdk-build-playbook.md §6 模板生成**，不可自己拼 API：

1. **MainActivity.java**: 基于 `references/android-mainactivity-template.java`（140+ 行完整可跑模板）
2. **AndroidManifest.xml**: playbook §6.4（4 权限 + Activity）
3. **activity_main.xml**: 容器 ViewGroup（给 setRenderArea 用，避免黑屏）
4. **strings.xml / values**: 基础资源
5. **credentials.json**: 放 assets/，内容见 playbook §6.5
6. **proguard-rules.pro**: 保留虚拟人 SDK 类

## Step 6: 设置 local.properties

```properties
sdk.dir=C\:\\Android\\Sdk
```

## Step 7: 构建验证

```bash
cd <工程根目录>
./gradlew assembleDebug
```

预期：首次 3-5 分钟（下载 AGP + AndroidX），增量秒级。

## 关键约束（HARD-GATE）

1. **API 必须按 playbook §1 真实签名**，禁用以下不存在的 API：
   - ❌ `sendText(text)` → ✅ `writeText(text, TextParams)`
   - ❌ `createStreamPlayer(ctx, view)` → ✅ `createPlayer(ctx, "xrtc")` + `setRenderArea(容器)`
   - ❌ `onNlpResult/onAsrResult/onAvatarReady` → ✅ `IAvatarListener.onResult/onEvent/onError`

2. **代码写完必须 grep 黑名单**:
   ```bash
   grep -r "createStreamPlayer\|sendText\|onNlpResult\|onAsrResult" app/src/
   ```
   命中即报错，必须改写。

3. **credentials.json 必须加入 .gitignore**（模板已包含）

4. **gradle.properties 六项配置必须就位**（模板已包含）

## 常见错误与修复

| 错误 | 根因 | 修复 |
|------|------|------|
| 编译 20+ 分钟 | 未用 daemon | 检查 gradle.properties 是否有 `org.gradle.daemon=true` |
| 黑屏 | 未 setRenderArea | 用 `createPlayer("xrtc")` + `setRenderArea(容器ViewGroup)` |
| duplicate .so | 手动放了 webrtc .so | 删除 src/main/jniLibs 下的 .so，只靠 AAR 提供 |
| wrapper 下载失败 | 已预置 jar | 不应出现，检查模板是否完整复制 |

## 输出清单

构建完成后应有：
- `app/build/outputs/apk/debug/app-debug.apk`（可安装的 APK）
- 无编译错误，无 API 找不到错误
- logcat 显示 `initialize` 成功、`onEvent type=frame_start`
