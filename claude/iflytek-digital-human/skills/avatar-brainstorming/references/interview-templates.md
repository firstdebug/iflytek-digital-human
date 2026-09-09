# Phase 4: 需求访谈与方案探讨

**目的**: 通过交互式访谈，明确技术选型和实现细节

## 4.1 首次接入访谈

**访谈主题**:

**主题 1: 核心功能确认**
```
AskUserQuestion:
  question: "需要实现哪些功能？（可多选）"
  options:
    - label: "文本驱动播报"
      description: "虚拟人朗读指定文本"
    - label: "文本交互（NLP）"
      description: "文本经大模型理解后智能回答，需开通大模型对话能力"
    - label: "语音交互"
      description: "用户语音提问，虚拟人回答，需麦克风权限"
    - label: "全双工对话"
      description: "实时语音识别与交互，需开通全双工能力"
    - label: "动作控制"
      description: "虚拟人做手势、表情等动作"
  multiSelect: true
```

**主题 2: 视觉效果选择**
```
AskUserQuestion:
  question: "是否需要透明背景？"
  options:
    - label: "是"
      description: "虚拟人背景透明，可叠加到其他内容上（仅 XRTC 协议支持）"
    - label: "否"
      description: "使用默认背景或自定义背景图"
```

**主题 3: 协议选择**（Web/Android/iOS）
```
AskUserQuestion:
  question: "选择视频流协议（推荐）"
  options:
    - label: "XRTC（推荐）"
      description: "低延迟，支持透明背景"
    - label: "WebRTC"
      description: "通用协议，不支持透明背景"
  default: "XRTC"
```

**主题 4: 形象和声音**（如果 preflight 已验证，显示可用列表）
```
从 dev-env.yaml 读取已验证的资源:
  avatarId: "118801001"
  vcn: "x4_yezi"

询问是否更换:
  "使用形象 118801001 和发音人 x4_yezi？"
  - 是（使用已验证资源）
  - 否（选择其他，需重新验证授权）
```

---

## 4.2 功能扩展访谈

**访谈主题**:

**主题 1: 确认当前状态**
```
从代码扫描结果确认:
  existing_features: [text_driver, text_interact]
  existing_config:
    protocol: "xrtc"
    avatarId: "xxx"
    vcn: "xxx"

向用户确认:
  "检测到已实现文本驱动和文本交互，是否正确？"
```

**主题 2: 目标功能需求**
```
AskUserQuestion:
  question: "希望添加哪些功能？"
  options:
    - label: "语音交互"
      description: "用户语音提问，需麦克风权限和 ASR 能力"
    - label: "动作控制"
      description: "虚拟人手势、表情等动作"
    - label: "透明背景"
      description: "需使用 XRTC 协议，当前协议: ${current_protocol}"
    - label: "字幕显示"
      description: "云端生成字幕或客户端自行渲染"
  multiSelect: true
```

**主题 3: 增量实施风险评估**
```
if (新功能需要更改现有配置) {
  警告用户:
    "添加透明背景需要将协议从 webrtc 改为 xrtc，可能影响现有功能。
     建议创建独立分支测试。"
  
  AskUserQuestion:
    "是否继续？"
    - 是（生成增量方案）
    - 否（取消或调整需求）
}
```

---

## 4.3 配置调整访谈

**访谈主题**:

**主题 1: 调整目标确认**
```
用户需求: "想调整视频分辨率"

识别参数:
  current_resolution: "720x1280"
  
AskUserQuestion:
  question: "希望调整到什么分辨率？"
  options:
    - label: "1080x1920 (1080P)"
      description: "更清晰，但需要更高带宽"
    - label: "540x960 (540P)"
      description: "降低带宽，适合弱网环境"
  input_type: "custom"  # 允许自定义输入
```

**主题 2: 配置影响说明**
```
生成影响分析:
  "调整分辨率到 1080x1920 将影响:
   - 视频码率建议同步调整到 3000-4000
   - 网络带宽需求增加约 50%
   - 解码性能要求提高"

确认用户理解并同意
```

---

## Android 平台访谈增强（API Level 确认）

**触发条件**: Phase 4 需求访谈阶段，当判定目标平台为 Android 时

### 目标设备 Android 版本确认

**问题**:
"你的目标 Android 设备系统版本是？（或最低支持版本）"

**AskUserQuestion 选项**:
```yaml
question: "你的目标 Android 设备系统版本是？这会影响权限配置和 API 兼容性。"
header: "Android 版本"
multiSelect: false
options:
  - label: "Android 12+ (API 31+)"
    description: "需额外申请 BLUETOOTH_CONNECT 权限（XRTC 必需），日志路径自动适配分区存储。"
  
  - label: "Android 11 (API 30)"
    description: "需适配分区存储（日志路径改用应用私有目录），权限配置标准。"
  
  - label: "Android 8-10 (API 26-29)"
    description: "标准配置，无特殊适配要求。"
  
  - label: "Android 5-7 (API 21-25)"
    description: "虚拟人 SDK 最低支持版本，部分新特性不可用。"
```

### 根据 API Level 自动调整配置

```python
def adjust_config_by_api_level(api_level):
    """根据目标 API Level 自动调整配置"""
    config = {
        "permissions": ["INTERNET", "ACCESS_NETWORK_STATE", "RECORD_AUDIO"],
        "log_path_strategy": "default",
        "permission_helper_template": "standard"
    }
    
    # Android 12+ (API 31+)
    if api_level >= 31:
        config["permissions"].append("BLUETOOTH_CONNECT")  # XRTC 必需
        config["log_path_strategy"] = "scoped_storage"  # 使用 getExternalFilesDir()
        config["permission_helper_template"] = "api31+"
    
    # Android 11 (API 30)
    elif api_level >= 30:
        config["log_path_strategy"] = "scoped_storage"
    
    # Android 5-12 (API 21-30)
    else:
        config["permissions"].extend(["READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE"])
        config["log_path_strategy"] = "legacy_sdcard"  # 仍可用 /sdcard/
    
    # Android 13+ (API 33+) 废弃存储权限
    if api_level >= 33:
        config["permissions"] = [p for p in config["permissions"] 
                                if p not in ["READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE"]]
    
    return config
```

### 配置生成影响

根据用户选择的 API Level，自动调整：

#### 1. AndroidManifest.xml 权限声明
```xml
<!-- API 31+ 自动添加 -->
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>

<!-- API 21-32 保留，API 33+ 移除 -->
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"/>
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"/>
```

#### 2. PermissionHelper 动态权限列表
```java
// API 31+ 版本
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
    perms.add(Manifest.permission.BLUETOOTH_CONNECT);
}

// API 21-32 版本
if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
    perms.add(Manifest.permission.READ_EXTERNAL_STORAGE);
    perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE);
}
```

#### 3. 日志路径策略
```java
// API 30+ 版本
String logPath = getExternalFilesDir(null).getAbsolutePath() + "/log/";

// API 21-29 版本（可选）
String logPath = "/sdcard/iflytek/log/";  // 仍可用但不推荐
```

### 用户提示

访谈完成后，根据选择给出提示：
```
✅ 目标 Android 版本: Android 12+ (API 31+)

自动调整配置:
  - ✅ 已添加 BLUETOOTH_CONNECT 权限（XRTC 必需）
  - ✅ 日志路径使用应用私有目录（适配分区存储）
  - ✅ PermissionHelper 动态构建权限列表（按 API Level）

如果后续需要支持更低版本，请重新运行 avatar-brainstorming 并选择对应版本。
```

