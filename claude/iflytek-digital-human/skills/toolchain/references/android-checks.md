# Android 平台工具链检查

Android 分支的检查项清单、检测脚本、配置 / 修复模板、编排流程与状态分类、输出格式、常见问题修复。
骨架与 `summarizeStatus` 通用实现见 `../SKILL.md`；本文件只承载 Android 特定载荷。

---

## 检查项清单

| # | 检查项 | 重要性 | required | 关键判据 |
|---|--------|--------|----------|----------|
| 1 | Gradle 环境 | ⭐⭐⭐ | 是 | 按 JDK 分档（见下版本矩阵）；JDK17→Gradle 8.0+ |
| 2 | Android SDK | ⭐⭐⭐ | 是 | ANDROID_HOME 已设，minSdkVersion ≥ 21（推荐 26） |
| 3 | JDK 环境 | ⭐⭐⭐ | 是 | JDK 8+（推荐 17；JDK17 需 AGP 8.1+） |
| 4 | NDK 环境 | ⭐⭐ | 否 | 仅使用 Native 代码时需要 |
| 5 | ABI 配置 | ⭐⭐⭐ | — | 仅支持 armeabi-v7a / arm64-v8a |
| 6 | 依赖检查 | ⭐⭐⭐ | 是 | okhttp 3.11.0+（必需），gson 可选 |
| 7 | 构建配置 | ⭐⭐ | — | jniLibs.srcDirs 含 'libs' 必需 |
| 8 | gradle.properties 性能 | ⭐⭐⭐ | 是 | daemon/parallel/caching 必配（否则编译极慢） |
| 9 | 签名配置 | ⭐⭐ | — | Release 版本必需 |

检查优先级：Gradle / Android SDK / JDK = Critical；依赖 / 性能配置 = High；ABI = Medium（推荐）；签名 = Low（发布时必需）。

### ⚠️ 版本矩阵（按 JDK 分档，必须匹配否则同步失败）
| JDK | AGP | Gradle | compileSdk | 说明 |
|-----|-----|--------|-----------|------|
| **17** | **8.1.4** | **8.0.2** | 34 | 推荐；本平台已验证组合。**JDK17 配 Gradle 7.x 会同步失败** |
| 11 | 7.x | 7.4–7.6 | 33 | 兼容旧工程 |
| 8 | 4.x–7.0 | 6.x–7.0 | 30- | 不推荐 |

平台差异：Windows 使用 `gradlew.bat`，macOS/Linux 使用 `./gradlew`，注意路径分隔符。
**编译规范（HARD-GATE）**：永远用 `gradlew`（复用 daemon），**严禁 `--no-daemon`**（会全量、极慢，实测 22 分钟）。

---

## 1. Gradle 环境

**检查方法**:
```bash
# 1. 检查 Gradle Wrapper
if [ -f "./gradlew" ]; then
  ./gradlew --version
else
  gradle --version
fi
```

**要求**:
```yaml
required: true
minimum_version: "7.0"
recommended_version: "7.4+"
gradle_plugin_version: "7.2+"  # Android Gradle Plugin
```

**判断**:
```javascript
const gradleVersion = execSync('./gradlew --version').toString();
const versionMatch = gradleVersion.match(/Gradle (\d+\.\d+)/);

if (!versionMatch) {
  return { status: 'not_found', 
           fix: '安装 Gradle 或使用 Android Studio 自带的 Gradle' };
}

const version = parseFloat(versionMatch[1]);

if (version >= 7.4) {
  return { status: 'optimal', version };
} else if (version >= 7.0) {
  return { status: 'acceptable', version,
           note: '建议升级到 Gradle 7.4+' };
} else {
  return { status: 'outdated', version,
           fix: '升级到 Gradle 7.0+，修改 gradle/wrapper/gradle-wrapper.properties' };
}
```

**修复建议**:
```bash
# 升级 Gradle Wrapper
# gradle/wrapper/gradle-wrapper.properties
distributionUrl=https\://services.gradle.org/distributions/gradle-7.6-bin.zip
```

---

**国内镜像加速（推荐）**:
```properties
# gradle/wrapper/gradle-wrapper.properties

# ✅ 腾讯云镜像（推荐，速度快）
distributionUrl=https\://mirrors.cloud.tencent.com/gradle/gradle-7.5-bin.zip

# ✅ 阿里云镜像（备用）
distributionUrl=https\://mirrors.aliyun.com/gradle/gradle-7.5-bin.zip

# ❌ 官方源（国内慢，仅备用）
distributionUrl=https\://services.gradle.org/distributions/gradle-7.5-bin.zip
```

**Maven 依赖加速（build.gradle）**:
```gradle
allprojects {
    repositories {
        // ✅ 阿里云镜像（推荐）
        maven { url 'https://maven.aliyun.com/repository/google' }
        maven { url 'https://maven.aliyun.com/repository/public' }
        
        // 官方源（备用）
        google()
        mavenCentral()
    }
}
```

## 2. Android SDK 环境

**检查方法**:
```bash
# 1. 检查 ANDROID_HOME 环境变量
echo $ANDROID_HOME
# 或 ANDROID_SDK_ROOT
echo $ANDROID_SDK_ROOT

# 2. 检查 SDK 工具
$ANDROID_HOME/tools/bin/sdkmanager --list
```

**要求**:
```yaml
required: true
min_sdk_version: 21  # 虚拟人 SDK 要求
compile_sdk_version: 33
target_sdk_version: 33
build_tools_version: "33.0.0+"
```

**判断**:
```javascript
const androidHome = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;

if (!androidHome) {
  return { 
    status: 'not_found',
    fix: '设置 ANDROID_HOME 环境变量指向 Android SDK 目录'
  };
}

// 检查 build.gradle 配置
const buildGradle = fs.readFileSync('app/build.gradle', 'utf-8');
const minSdkMatch = buildGradle.match(/minSdkVersion\s+(\d+)/);
const compileSdkMatch = buildGradle.match(/compileSdkVersion\s+(\d+)/);

if (minSdkMatch && parseInt(minSdkMatch[1]) < 21) {
  return {
    status: 'min_sdk_too_low',
    current: minSdkMatch[1],
    required: 21,
    fix: 'app/build.gradle 中设置 minSdkVersion 21'
  };
}

return { status: 'ok', androidHome };
```

**修复建议**:
```bash
# 1. 安装 Android SDK（通过 Android Studio）
# 或手动下载 command line tools

# 2. 设置环境变量
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools

# 3. 配置 build.gradle
android {
    compileSdkVersion 33
    defaultConfig {
        minSdkVersion 21
        targetSdkVersion 33
    }
}
```

---

## 3. JDK 环境

**检查方法**:
```bash
java -version
javac -version
```

**要求**:
```yaml
required: true
minimum_version: "8"
recommended_version: "11"
optimal_version: "17"
```

**判断**:
```javascript
const javaVersion = execSync('java -version 2>&1').toString();
const versionMatch = javaVersion.match(/version "(\d+)/);

if (!versionMatch) {
  return { status: 'not_found', 
           fix: '安装 JDK 8+' };
}

const majorVersion = parseInt(versionMatch[1]);

if (majorVersion >= 17) {
  return { status: 'optimal', version: majorVersion };
} else if (majorVersion >= 11) {
  return { status: 'recommended', version: majorVersion };
} else if (majorVersion >= 8) {
  return { status: 'acceptable', version: majorVersion,
           note: '建议升级到 JDK 11 或 17' };
} else {
  return { status: 'too_old', version: majorVersion,
           fix: '升级到 JDK 8+' };
}
```

---

## 4. NDK 环境（可选）

**检查方法**:
```bash
# 检查 NDK 安装
ls $ANDROID_HOME/ndk/
# 或读取 local.properties
cat local.properties | grep ndk.dir
```

**要求**:
```yaml
required: false  # 虚拟人 SDK 不直接需要 NDK
recommended_version: "21.0+"
use_case: "使用 Native 音视频处理时"
```

**判断**:
```javascript
// 检查是否使用了 NDK
const buildGradle = fs.readFileSync('app/build.gradle', 'utf-8');
const usesNdk = buildGradle.includes('ndk') || 
                buildGradle.includes('externalNativeBuild');

if (!usesNdk) {
  return { status: 'not_needed', 
           note: '虚拟人 SDK 不需要 NDK' };
}

// 检查 NDK 安装
const ndkDir = process.env.ANDROID_NDK_HOME || 
               `${androidHome}/ndk`;

if (fs.existsSync(ndkDir)) {
  return { status: 'installed', path: ndkDir };
} else {
  return { status: 'not_found',
           fix: '通过 Android Studio SDK Manager 安装 NDK' };
}
```

---

## 5. ABI 配置检查

**检查方法**: 读取 `app/build.gradle`

```javascript
const buildGradle = fs.readFileSync('app/build.gradle', 'utf-8');

// 检查 abiFilters 配置
const abiMatch = buildGradle.match(/abiFilters\s+['"](.+?)['"]/g);

if (abiMatch) {
  const abis = abiMatch.map(m => m.match(/['"](.+?)['"]/)[1]);
  console.log('配置的 ABI:', abis);
  
  // 虚拟人 SDK 支持的 ABI
  const supportedAbis = ['armeabi-v7a', 'arm64-v8a'];
  const unsupported = abis.filter(abi => !supportedAbis.includes(abi));
  
  if (unsupported.length > 0) {
    return {
      status: 'unsupported_abi',
      unsupported,
      fix: '虚拟人 SDK 仅支持 armeabi-v7a 和 arm64-v8a'
    };
  }
  
  return { status: 'configured', abis };
} else {
  return {
    status: 'not_configured',
    note: '未配置 ABI，将打包所有架构（APK 体积较大）',
    recommendation: '配置 abiFilters 减小 APK 体积'
  };
}
```

**推荐配置**:
```gradle
android {
    defaultConfig {
        ndk {
            abiFilters 'armeabi-v7a', 'arm64-v8a'
        }
    }
}
```

---

## 6. 依赖检查

**检查方法**: 读取 `app/build.gradle`

```javascript
const buildGradle = fs.readFileSync('app/build.gradle', 'utf-8');

const requiredDeps = {
  'okhttp': {
    pattern: /com\.squareup\.okhttp3:okhttp:[\d.]+/,
    minVersion: '3.11.0',
    purpose: '虚拟人 SDK 网络通信'
  },
  'gson': {
    pattern: /com\.google\.code\.gson:gson:[\d.]+/,
    minVersion: '2.8.0',
    purpose: 'JSON 解析（可选）',
    required: false
  }
};

const missingDeps = [];
const outdatedDeps = [];

for (const [name, dep] of Object.entries(requiredDeps)) {
  if (!buildGradle.match(dep.pattern)) {
    if (dep.required !== false) {
      missingDeps.push({ name, ...dep });
    }
  } else {
    // 检查版本（简化示例）
    const versionMatch = buildGradle.match(new RegExp(`${name}:([\\d.]+)`));
    if (versionMatch && versionMatch[1] < dep.minVersion) {
      outdatedDeps.push({ name, current: versionMatch[1], min: dep.minVersion });
    }
  }
}

if (missingDeps.length > 0) {
  return {
    status: 'missing_dependencies',
    missing: missingDeps,
    fix: '在 app/build.gradle 中添加缺失的依赖'
  };
}

if (outdatedDeps.length > 0) {
  return {
    status: 'outdated_dependencies',
    outdated: outdatedDeps,
    fix: '升级过时的依赖版本'
  };
}

return { status: 'dependencies_ok' };
```

**修复建议**:
```gradle
dependencies {
    // 必需依赖
    implementation 'com.squareup.okhttp3:okhttp:3.11.0'
    
    // 虚拟人 SDK AAR
    implementation fileTree(include: ['*.jar', '*.aar'], dir: 'libs')
}
```

---

## 7. 构建配置检查

**检查方法**: 读取 `app/build.gradle`

```javascript
const buildGradle = fs.readFileSync('app/build.gradle', 'utf-8');

const checks = {
  jniLibs: {
    pattern: /jniLibs\.srcDirs\s*=\s*\['libs'\]/,
    required: true,
    fix: 'android { sourceSets { main { jniLibs.srcDirs = [\'libs\'] } } }'
  },
  
  multiDexEnabled: {
    pattern: /multiDexEnabled\s+true/,
    required: false,
    note: '方法数超过 64K 时需要'
  },
  
  packagingOptions: {
    pattern: /packagingOptions/,
    required: false,
    note: '避免重复文件冲突'
  }
};

const issues = [];

for (const [name, check] of Object.entries(checks)) {
  if (check.required && !buildGradle.match(check.pattern)) {
    issues.push({
      name,
      severity: 'high',
      fix: check.fix
    });
  }
}

if (issues.length > 0) {
  return { status: 'build_config_issues', issues };
}

return { status: 'build_config_ok' };
```

**推荐配置**:
```gradle
android {
    sourceSets {
        main {
            jniLibs.srcDirs = ['libs']  // 必需：加载 so 库
        }
    }
    
    defaultConfig {
        multiDexEnabled true  // 方法数超 64K 时需要
    }
    
    packagingOptions {
        pickFirst 'lib/armeabi-v7a/libc++_shared.so'
        pickFirst 'lib/arm64-v8a/libc++_shared.so'
    }
}
```

---

## 8. gradle.properties 性能配置检查（HARD-GATE：编译不卡的关键）

**检查方法**: 读取 `gradle.properties`，确认以下六项就位。

**要求**:
```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.daemon=true          # 复用守护进程（缺失或 --no-daemon 会每次全量, 实测 22 分钟）
org.gradle.parallel=true        # 并行模块构建
org.gradle.caching=true         # 构建缓存, 增量秒级
org.gradle.configureondemand=true
android.useAndroidX=true
```

**判断**:
```javascript
const gp = fs.existsSync('gradle.properties') ? fs.readFileSync('gradle.properties','utf-8') : '';
const need = ['org.gradle.daemon=true','org.gradle.parallel=true','org.gradle.caching=true'];
const missing = need.filter(k => !gp.includes(k));
if (missing.length) return { status: 'perf_config_missing', missing,
  fix: '写入 gradle.properties 六项性能配置；编译用 gradlew 且严禁 --no-daemon' };
return { status: 'perf_config_ok' };
```

**血泪根因**：本平台实测首次 `assembleDebug` 耗时 **22 分钟**，根因是 `--no-daemon` + 无性能配置。
配齐后首次约 3-5 分钟（含 AGP/依赖下载）、增量秒级。**镜像加速**：settings.gradle 加
`maven { url 'https://maven.aliyun.com/repository/google' }` 与 `.../public` 加速首次依赖。

---

## 9. 签名配置检查

**检查方法**: 读取 `app/build.gradle`

```javascript
const buildGradle = fs.readFileSync('app/build.gradle', 'utf-8');

const hasSigningConfig = buildGradle.includes('signingConfigs');
const hasReleaseConfig = buildGradle.match(/release\s*{[\s\S]*?signingConfig/);

if (!hasSigningConfig) {
  return {
    status: 'no_signing_config',
    note: 'Debug 版本可选，Release 版本必需',
    fix: '配置 signingConfig 用于 Release 构建'
  };
}

if (!hasReleaseConfig) {
  return {
    status: 'release_not_signed',
    fix: 'Release 构建类型未关联签名配置'
  };
}

return { status: 'signing_configured' };
```

**推荐配置**:
```gradle
android {
    signingConfigs {
        release {
            storeFile file("your-keystore.jks")
            storePassword "your-password"
            keyAlias "your-alias"
            keyPassword "your-password"
        }
    }
    
    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
        }
    }
}
```

---

## 完整检查流程（编排）

```javascript
async function checkAndroidToolchain() {
  const results = {
    platform: 'android',
    checks: {}
  };
  
  // 1. Gradle 环境
  results.checks.gradle = await checkGradle();
  
  // 2. Android SDK
  results.checks.android_sdk = await checkAndroidSDK();
  
  // 3. JDK 环境
  results.checks.jdk = await checkJDK();
  
  // 4. NDK 环境（可选）
  results.checks.ndk = await checkNDK();
  
  // 5. ABI 配置
  results.checks.abi = await checkABI();
  
  // 6. 依赖检查
  results.checks.dependencies = await checkDependencies();
  
  // 7. 构建配置
  results.checks.build_config = await checkBuildConfig();
  
  // 8. 签名配置
  results.checks.signing = await checkSigning();
  
  // 汇总状态（summarizeStatus 通用骨架见 ../SKILL.md）
  results.status = summarizeStatus(results.checks);
  
  return results;
}
```

## 状态分类（填入通用 summarizeStatus）

Android 分支在通用 `summarizeStatus` 骨架的「平台特定分类规则」处填入：

```javascript
// Gradle 未安装
if (checks.gradle.status === 'not_found') {
  critical.push('Gradle 未安装');
}

// Android SDK 未配置
if (checks.android_sdk.status === 'not_found') {
  critical.push('Android SDK 未配置');
}

// minSdkVersion 过低
if (checks.android_sdk.status === 'min_sdk_too_low') {
  critical.push('minSdkVersion < 21');
}

// JDK 版本问题
if (checks.jdk.status === 'not_found') {
  critical.push('JDK 未安装');
}

// 依赖缺失
if (checks.dependencies.status === 'missing_dependencies') {
  critical.push('缺少必需依赖');
}

// 构建配置问题
if (checks.build_config.status === 'build_config_issues') {
  warnings.push('构建配置不完整');
}

// ABI 配置建议
if (checks.abi.status === 'not_configured') {
  warnings.push('建议配置 ABI 减小 APK 体积');
}
```

HARD-GATE：`minSdkVersion 21` 为硬性要求，< 21 判 critical；Gradle / Android SDK / JDK
任一未装判 critical，阻断后续流程；必需依赖 okhttp（3.11.0+）缺失判 critical；SDK 仅支持
ABI `armeabi-v7a` / `arm64-v8a`（出现其它判 `unsupported_abi`）；`jniLibs.srcDirs = ['libs']`
为加载 so 库的必需构建配置，缺失属高危。

Red Flags：minSdkVersion < 21（不兼容 SDK）；打包不受支持 ABI（如 x86 / x86_64，so 库无法加载）；
未配置 jniLibs.srcDirs 或 AAR 未通过 fileTree 引入（运行期 UnsatisfiedLinkError）；
Release 构建未关联签名配置（无法发布）。

---

## 输出格式

### 成功输出
```yaml
status: "all_ok"
platform: "android"
checks:
  gradle:
    status: "optimal"
    version: "7.6"
  android_sdk:
    status: "ok"
    min_sdk: 21
    compile_sdk: 33
  jdk:
    status: "recommended"
    version: 11
  abi:
    status: "configured"
    abis: ["armeabi-v7a", "arm64-v8a"]
  dependencies:
    status: "dependencies_ok"
  build_config:
    status: "build_config_ok"
```

### 关键问题输出
```yaml
status: "critical_issues"
issues:
  - "minSdkVersion < 21"
  - "缺少必需依赖"
checks:
  android_sdk:
    status: "min_sdk_too_low"
    current: 19
    required: 21
    fix: "app/build.gradle 中设置 minSdkVersion 21"
  dependencies:
    status: "missing_dependencies"
    missing:
      - name: "okhttp"
        minVersion: "3.11.0"
        purpose: "虚拟人 SDK 网络通信"
    fix: "implementation 'com.squareup.okhttp3:okhttp:3.11.0'"
```

---

## 常见问题修复

### 1. Gradle 同步失败

**原因**:
- 网络问题
- Gradle 版本不兼容
- 依赖下载失败

**解决**:
```bash
# 1. 清理缓存
./gradlew clean

# 2. 使用国内镜像
# build.gradle (project level)
allprojects {
    repositories {
        maven { url 'https://maven.aliyun.com/repository/public/' }
        maven { url 'https://maven.aliyun.com/repository/google/' }
        google()
        mavenCentral()
    }
}

# 3. 重新同步
./gradlew build --refresh-dependencies
```

### 2. AAR 未被识别

**原因**:
- libs 目录未配置
- fileTree 未包含 *.aar

**解决**:
```gradle
android {
    sourceSets {
        main {
            jniLibs.srcDirs = ['libs']
        }
    }
}

dependencies {
    implementation fileTree(include: ['*.jar', '*.aar'], dir: 'libs')
}
```

### 3. UnsatisfiedLinkError

**原因**:
- so 库未打包到 APK
- ABI 不匹配

**解决**:
```gradle
android {
    defaultConfig {
        ndk {
            abiFilters 'armeabi-v7a', 'arm64-v8a'
        }
    }
    
    packagingOptions {
        pickFirst 'lib/armeabi-v7a/libc++_shared.so'
        pickFirst 'lib/arm64-v8a/libc++_shared.so'
    }
}
```

