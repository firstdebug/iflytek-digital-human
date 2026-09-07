# Android Gradle 稳定构建规范

用于 Android 虚拟人工程的 Gradle Wrapper 下载、Maven 依赖解析、daemon/缓存锁、内存和构建超时处理。构建、预检、排障和交付验证必须共用本规范。

## 不变量

1. 同一工程同一时间只运行一个 Gradle 调用。把测试和 APK 构建合并到同一命令，不并行启动 Debug、Release 或第二次重试。
2. 使用工程 Wrapper，不使用系统 Gradle，不加 `--no-daemon`。
3. 命令超时不代表 Gradle 已停止。先检查原进程、daemon、缓存锁和产物时间，再决定等待或停止；不得立即重复执行同一命令。
4. 冷缓存先在线预热，成功后再用 `--offline` 做最终验收。冷缓存不得直接离线构建。
5. 不把 `clean`、`--refresh-dependencies`、删除 `.gradle` 或杀死全部 Java 进程作为首选修复；这些操作会放大下载量、全量重编译或误伤其他工程。

## 保守默认配置

单模块工程或内存未知的机器默认使用：

```properties
org.gradle.jvmargs=-Xmx1280m -Dfile.encoding=UTF-8
org.gradle.daemon=true
org.gradle.parallel=false
org.gradle.workers.max=2
org.gradle.caching=true
org.gradle.configureondemand=true
android.useAndroidX=true
```

`parallel=true` 只适用于内存充足的多模块工程。单模块项目通常没有收益，反而会增加峰值内存和缓存争用。确认机器有足够可用内存后才提高 `Xmx` 或 worker 数，并一次只改一个参数。

## 国内镜像顺序

Wrapper 使用与工程版本完全一致的腾讯镜像，例如：

```properties
distributionUrl=https\://mirrors.cloud.tencent.com/gradle/gradle-8.0.2-bin.zip
networkTimeout=60000
```

修改前用 HEAD 请求确认镜像文件返回 200，且不要改变 Gradle 版本号。Maven 在 `pluginManagement.repositories` 和 `dependencyResolutionManagement.repositories` 中统一使用：

```gradle
maven { url 'https://maven.aliyun.com/repository/gradle-plugin' } // pluginManagement only
maven { url 'https://maven.aliyun.com/repository/google' }
maven { url 'https://maven.aliyun.com/repository/public' }
maven { url 'https://mirrors.cloud.tencent.com/nexus/repository/maven-public/' }
maven { url 'https://repo.huaweicloud.com/repository/maven/' }
google()
mavenCentral()
```

顺序固定为阿里云、腾讯云、华为云、官方兜底。某个镜像缺少构件时让 Gradle继续尝试后续仓库，不要删除官方兜底。

## 构建状态机

### 1. 启动前

- 读取 Wrapper URL、Maven 仓库顺序和 `gradle.properties`。
- 检查是否已有同工程 Gradle 命令或 `GradleDaemon` 正在执行任务。
- 已有构建仍在消耗 CPU/网络或产物时间仍更新时，续接并轮询原会话，不启动第二个构建。
- 只有确认 daemon 已失去任务且锁长期不释放时，才运行一次 `gradlew --stop`；不得在活动构建期间停止 daemon。

### 2. 冷缓存在线预热

Windows：

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug --console=plain --stacktrace
```

macOS/Linux：

```bash
./gradlew :app:testDebugUnitTest :app:assembleDebug --console=plain --stacktrace
```

将长任务保持为同一个可轮询进程。工具调用达到等待时限后续接该会话，不要再发起新的 Gradle 命令。

### 3. 热缓存离线验收

在线构建成功后执行一次：

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug --offline --console=plain
```

离线失败并提示缺少模块，说明缓存未预热完整；回到在线预热补齐依赖。Debug 成功不代表 Release 所需的 Lint 组件已缓存。需要 Release 时，在 Debug 完成后单独执行在线 `:app:assembleRelease`，成功后再离线复验，不能与 Debug 并发。

## 卡住诊断

| 现象 | 常见原因 | 处理 |
|---|---|---|
| Gradle banner 前长期无任务输出 | Wrapper ZIP 下载慢或镜像失效 | 检查 `distributionUrl`、HEAD 状态、Wrapper 缓存目录和网络流量 |
| `Resolve dependencies` 或首个 task 前停留 | Maven 仓库慢、冷缓存、Lint/插件首次下载 | 核对镜像顺序；保持原进程运行；用 `--info` 仅做一次诊断 |
| 出现 `Waiting to acquire lock` | 上一个 Gradle/daemon 仍持有缓存锁 | 查原构建是否仍活跃；等待或确认僵死后 `gradlew --stop`，禁止并发重跑 |
| daemon disappeared、频繁 GC、机器换页 | 堆或 worker 过大、并发构建 | 回到 1280 MB、2 workers、parallel=false，结束重复构建后重试 |
| Debug 很快、Release 首次很慢 | Release 首次解析 Lint/打包依赖 | 单独在线完成 Release 预热，之后离线复验 |
| 第二次离线构建数秒完成 | 缓存和增量构建正常 | 记录为稳定，不再清缓存或刷新依赖 |

## 超时后的强制流程

1. 不重跑命令。
2. 检查原工具会话是否仍可等待；可等待就继续轮询同一会话。
3. 检查 Gradle/Java 进程、CPU/网络活动、daemon 状态、APK 与测试报告时间。
4. 仍有进展就继续等待并向用户更新当前阶段。
5. 确认无进展且无活动任务后，停止该工程 daemon，再启动一次新的单一构建。
6. 记录实际根因是下载、锁、内存还是缺失依赖，不把笼统的“Gradle 卡住”作为结论。

## 禁止项

- 禁止同时运行两个 `gradlew` 命令。
- 禁止命令超时后直接再次执行。
- 禁止无证据执行 `clean --refresh-dependencies`。
- 禁止递归删除全局 Gradle 缓存。
- 禁止用杀死全部 Java 进程代替识别具体 Gradle daemon。
- 禁止在缓存未完整时声称 `--offline` 可以修复下载问题。

## 报告字段

交付报告至少记录：Wrapper URL、Maven 仓库优先级、内存/worker/parallel 配置、在线预热命令结果、离线验收命令结果、是否发生超时或缓存锁、APK 路径和测试结果。首次下载耗时与代码编译耗时要分开描述。
