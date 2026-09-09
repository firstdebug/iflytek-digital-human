# Android 构建模板

预置的 Android Gradle 环境，包含：
- Gradle 8.0.2 wrapper（腾讯云镜像，避免下载失败）
- AGP 8.1.4（适配 JDK 17）
- 阿里云 maven 镜像（加速依赖下载）
- 性能优化配置（daemon/parallel/caching）

## 使用方式

1. 复制整个目录到目标工程根目录
2. 替换模板占位符：
   - `settings.gradle.template` 中的 `{{PROJECT_NAME}}`
   - `app-build.gradle.template` 中的 `{{PACKAGE_NAME}}`
3. 重命名 `.template` 文件去掉后缀
4. 创建 `app/` 目录和源码文件
5. 运行 `gradlew assembleDebug` 构建

## 版本要求

- JDK 17
- Android SDK（通过 local.properties 指定）

## 文件说明

| 文件 | 说明 |
|------|------|
| gradle/wrapper/gradle-wrapper.jar | 预置 jar，避免在线下载 |
| gradle/wrapper/gradle-wrapper.properties | 腾讯云镜像 URL |
| gradle.properties | 六项性能配置 |
| settings.gradle.template | 阿里云 maven 镜像 + 项目结构 |
| build.gradle.template | AGP 8.1.4 |
| app-build.gradle.template | app 模块配置（包含虚拟人 SDK 所需依赖） |
| gradlew / gradlew.bat | Gradle wrapper 脚本 |
| .gitignore | 排除构建产物和敏感凭据 |

## 首次构建耗时

- 首次：3-5 分钟（下载 AGP + AndroidX，走阿里云镜像）
- 增量：秒级（daemon + caching 生效）

## 生成此模板的时间

2025-01-24（对应 avatar-core-v3.2.7 + playbook 验证版本）
